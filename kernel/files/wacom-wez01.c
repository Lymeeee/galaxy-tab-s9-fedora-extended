// SPDX-License-Identifier: GPL-2.0
/*
 * Wacom WEZ01 EMR digitizer (S Pen) driver.
 *
 * The raw sec-wacom protocol comes from Samsung's GPL-2.0 downstream wacom
 * driver for the Galaxy Tab S9 (SM-X710), cross-checked against the Tab S8+
 * mainline port. Only pen reporting is implemented; the IC runs its
 * factory-flashed firmware, so no firmware download path is needed.
 *
 * Palm rejection: while the pen is in range (hovering or touching) the FTS
 * touchscreen must not report finger contacts.  Pen proximity is tracked
 * here and exported through wacom_wez01_should_suppress_touch(), which the
 * touchscreen driver queries before reporting fingers.
 */

#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/input.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/pm_wakeirq.h>
#include <linux/pm_wakeup.h>
#include <linux/power_supply.h>
#include <linux/property.h>
#include <linux/regulator/consumer.h>
#include <linux/sysfs.h>
#include <linux/timer.h>
#include <linux/unaligned.h>
#include <linux/wacom_wez01.h>
#include <linux/workqueue.h>

/* Calibration: the digitizer's usable matrix is inset from the glass;
 * these map the glass edges onto the panel.  Tunable for calibration. */
static int pen_x_min = 0;
static int pen_x_max = 23575;
static int pen_y_min = 0;
static int pen_y_max = 14724;
module_param(pen_x_min, int, 0644);
module_param(pen_x_max, int, 0644);
module_param(pen_y_min, int, 0644);
module_param(pen_y_max, int, 0644);

#define WEZ01_COM_SURVEY_EXIT		0x2d
#define WEZ01_COM_SAMPLERATE_STOP	0x30
#define WEZ01_COM_SAMPLERATE_START	0x31

/* Samsung's W90xx garage/dock and BLE ring protocol. */
#define WEZ01_CMD_BLE_CHARGE_ENABLE	0xe9
#define WEZ01_CMD_BLE_PAIR_RESET	0xea
#define WEZ01_CMD_BLE_CHARGE_START	0xeb
#define WEZ01_CMD_BLE_CHARGE_KEEP_ON	0xec
#define WEZ01_CMD_BLE_CHARGE_KEEP_OFF	0xed
#define WEZ01_CMD_GARAGE_STATUS		0xee
#define WEZ01_CHARGE_START_DELAY_MS	1000
#define WEZ01_CHARGE_STATUS_PERIOD_MS	30000
#define WEZ01_PKT_REPLY			0x0e
#define WEZ01_REPLY_GARAGE_CHARGE	0x06

/*
 * The keyboard folio's magnet never reaches the tablet's hall sensor; the
 * digitiser is what notices the cover.  The controller volunteers a 0x0d
 * notification frame with the cover state in bit 7 of data[3], exactly as
 * Samsung's downstream driver decodes it.
 */
#define WEZ01_PKT_NOTI			0x0d
#define WEZ01_NOTI_COVER_DETECT		0x0a
#define WEZ01_COVER_CLOSED		BIT(7)

enum wez01_charge_state {
	WEZ01_CHARGE_OFF = 0,
	WEZ01_CHARGE_START,
	WEZ01_CHARGE_TRANSIT,
	WEZ01_CHARGE_RESET,
	WEZ01_CHARGE_AFTER_START,
	WEZ01_CHARGE_AFTER_RESET,
	WEZ01_CHARGE_ON_KEEP_1,
	WEZ01_CHARGE_OFF_KEEP_1,
	WEZ01_CHARGE_ON_KEEP_2,
	WEZ01_CHARGE_OFF_KEEP_2,
	WEZ01_CHARGE_FULL,
};

/*
 * There is no query command at runtime: a raw 32-byte read returns the last
 * coordinate frame followed by the 16-byte query block, tagged by its header.
 */
#define WEZ01_QUERY_SIZE		32
#define WEZ01_QUERY_POS			16
#define WEZ01_QUERY_HEADER		0x0f

/* query block offsets */
#define WEZ01_QRY_X			1
#define WEZ01_QRY_Y			3
#define WEZ01_QRY_PRESSURE		5
#define WEZ01_QRY_FWVER			7
#define WEZ01_QRY_MPUVER		9
#define WEZ01_QRY_TILT_X		11
#define WEZ01_QRY_TILT_Y		12
#define WEZ01_QRY_HEIGHT		13

#define WEZ01_MPU_ID			0x46

/* event packets are 16 bytes, read with one ack byte appended */
#define WEZ01_EVENT_SIZE		16

/* packet id in byte 0 bits [3:0] */
#define WEZ01_PKT_COORD			1

/* coordinate packet byte 0 flags */
#define WEZ01_RDY			BIT(7)
#define WEZ01_ERASER			BIT(6)
#define WEZ01_SIDE			BIT(5)
#define WEZ01_TIP			BIT(4)

/* 100 units/mm across the 11" panel's active area; libinput requires it */
#define WEZ01_RES_UNITS_PER_MM		100

/*
 * The controller can fall silent without ever sending an out-of-range
 * frame; if that state never cleared, the touchscreen would stay disabled
 * for the rest of the session.  The pen sends idle frames roughly every
 * 25 ms while in range, so a quarter of a second of silence is safely
 * "pen gone" while never firing during real use.
 */
#define WEZ01_PROXIMITY_TIMEOUT_MS	250

struct wacom_wez01 {
	struct i2c_client *client;
	struct input_dev *input;
	struct gpio_desc *fwe;
	struct gpio_desc *pdct;
	struct power_supply *pen_supply;
	struct delayed_work charge_work;
	struct mutex command_lock;
	int pdct_irq;
	u16 max_x;
	u16 max_y;
	u16 max_pressure;
	u8 max_height;
	s8 max_tilt_x;
	s8 max_tilt_y;
	bool prox;
	bool docked;
	bool cover_closed;
	u8 charge_stage;
	int charge_status;
	struct timer_list prox_timer;
};

static atomic_t wez01_pen_proximity = ATOMIC_INIT(0);
static atomic_t wez01_touch_suppression = ATOMIC_INIT(1);

bool wacom_wez01_should_suppress_touch(void)
{
	return atomic_read(&wez01_touch_suppression) &&
	       atomic_read(&wez01_pen_proximity);
}
EXPORT_SYMBOL_GPL(wacom_wez01_should_suppress_touch);

static int wacom_wez01_send(struct wacom_wez01 *w, u8 cmd)
{
	int ret;

	mutex_lock(&w->command_lock);
	ret = i2c_master_send(w->client, &cmd, 1);
	mutex_unlock(&w->command_lock);
	if (ret < 0)
		return ret;
	if (ret != 1)
		return -EIO;

	return 0;
}

static int wacom_wez01_query(struct wacom_wez01 *w)
{
	u8 buf[WEZ01_QUERY_SIZE];
	const u8 *q = buf + WEZ01_QUERY_POS;
	int retry, ret;

	for (retry = 0; retry < 10; retry++) {
		ret = i2c_master_recv(w->client, buf, sizeof(buf));
		if (ret == sizeof(buf) && q[0] == WEZ01_QUERY_HEADER)
			break;

		msleep(20);
	}

	if (retry == 10)
		return ret < 0 ? ret : -EIO;

	w->max_x = get_unaligned_be16(&q[WEZ01_QRY_X]);
	w->max_y = get_unaligned_be16(&q[WEZ01_QRY_Y]);
	w->max_pressure = get_unaligned_be16(&q[WEZ01_QRY_PRESSURE]);
	w->max_tilt_x = q[WEZ01_QRY_TILT_X];
	w->max_tilt_y = q[WEZ01_QRY_TILT_Y];
	w->max_height = q[WEZ01_QRY_HEIGHT];

	if (q[WEZ01_QRY_MPUVER] != WEZ01_MPU_ID)
		dev_warn(&w->client->dev, "unexpected mpu id 0x%02x\n",
			 q[WEZ01_QRY_MPUVER]);

	dev_info(&w->client->dev,
		 "fw version 0x%04x, max_x %u, max_y %u, max_pressure %u\n",
		 get_unaligned_be16(&q[WEZ01_QRY_FWVER]),
		 w->max_x, w->max_y, w->max_pressure);

	return 0;
}

static int wacom_wez01_charge_status(u8 state)
{
	switch (state) {
	case WEZ01_CHARGE_FULL:
		return POWER_SUPPLY_STATUS_FULL;
	case WEZ01_CHARGE_START:
	case WEZ01_CHARGE_TRANSIT:
	case WEZ01_CHARGE_RESET:
	case WEZ01_CHARGE_AFTER_START:
	case WEZ01_CHARGE_AFTER_RESET:
	case WEZ01_CHARGE_ON_KEEP_1:
	case WEZ01_CHARGE_ON_KEEP_2:
		return POWER_SUPPLY_STATUS_CHARGING;
	case WEZ01_CHARGE_OFF:
	case WEZ01_CHARGE_OFF_KEEP_1:
	case WEZ01_CHARGE_OFF_KEEP_2:
		return POWER_SUPPLY_STATUS_NOT_CHARGING;
	default:
		return POWER_SUPPLY_STATUS_UNKNOWN;
	}
}

static enum power_supply_property wacom_wez01_pen_properties[] = {
	POWER_SUPPLY_PROP_STATUS,
	POWER_SUPPLY_PROP_PRESENT,
	POWER_SUPPLY_PROP_CAPACITY,
	POWER_SUPPLY_PROP_SCOPE,
	POWER_SUPPLY_PROP_MODEL_NAME,
};

static int wacom_wez01_pen_get_property(struct power_supply *psy,
					enum power_supply_property property,
					union power_supply_propval *value)
{
	struct wacom_wez01 *w = power_supply_get_drvdata(psy);

	switch (property) {
	case POWER_SUPPLY_PROP_STATUS:
		value->intval = READ_ONCE(w->charge_status);
		return 0;
	case POWER_SUPPLY_PROP_PRESENT:
		value->intval = READ_ONCE(w->docked);
		return 0;
	case POWER_SUPPLY_PROP_CAPACITY:
		if (READ_ONCE(w->charge_status) != POWER_SUPPLY_STATUS_FULL)
			return -ENODATA;
		value->intval = 100;
		return 0;
	case POWER_SUPPLY_PROP_SCOPE:
		value->intval = POWER_SUPPLY_SCOPE_DEVICE;
		return 0;
	case POWER_SUPPLY_PROP_MODEL_NAME:
		value->strval = "Samsung S Pen";
		return 0;
	default:
		return -EINVAL;
	}
}

static const struct power_supply_desc wacom_wez01_pen_supply = {
	.name = "gts9wifi-spen",
	.type = POWER_SUPPLY_TYPE_BATTERY,
	.properties = wacom_wez01_pen_properties,
	.num_properties = ARRAY_SIZE(wacom_wez01_pen_properties),
	.get_property = wacom_wez01_pen_get_property,
};

static void wacom_wez01_notify_garage(struct wacom_wez01 *w)
{
	sysfs_notify(&w->client->dev.kobj, NULL, "pen_docked");
	sysfs_notify(&w->client->dev.kobj, NULL, "pen_charging");
	if (w->pen_supply)
		power_supply_changed(w->pen_supply);
}

static void wacom_wez01_charge_work(struct work_struct *work)
{
	struct wacom_wez01 *w = container_of(to_delayed_work(work),
					     struct wacom_wez01, charge_work);
	int ret;

	if (!READ_ONCE(w->docked)) {
		w->charge_stage = 0;
		ret = wacom_wez01_send(w, WEZ01_CMD_BLE_CHARGE_KEEP_OFF);
		if (ret)
			dev_dbg(&w->client->dev,
				"could not stop S Pen charging: %d\n", ret);
		return;
	}

	if (w->charge_stage == 0) {
		ret = wacom_wez01_send(w, WEZ01_CMD_BLE_CHARGE_ENABLE);
		if (!ret) {
			usleep_range(20000, 25000);
			ret = wacom_wez01_send(w, WEZ01_CMD_BLE_CHARGE_START);
		}
		if (ret) {
			dev_warn(&w->client->dev,
				 "could not start S Pen charging: %d\n", ret);
			mod_delayed_work(system_wq, &w->charge_work,
					 msecs_to_jiffies(WEZ01_CHARGE_START_DELAY_MS));
			return;
		}

		w->charge_stage = 1;
		WRITE_ONCE(w->charge_status, POWER_SUPPLY_STATUS_CHARGING);
		wacom_wez01_notify_garage(w);
		dev_info(&w->client->dev, "S Pen charging started\n");
		mod_delayed_work(system_wq, &w->charge_work,
				 msecs_to_jiffies(WEZ01_CHARGE_START_DELAY_MS));
		return;
	}

	if (w->charge_stage == 1) {
		ret = wacom_wez01_send(w, WEZ01_CMD_BLE_CHARGE_KEEP_ON);
		if (ret) {
			dev_warn(&w->client->dev,
				 "could not keep S Pen charging: %d\n", ret);
			mod_delayed_work(system_wq, &w->charge_work,
					 msecs_to_jiffies(WEZ01_CHARGE_START_DELAY_MS));
			return;
		}
		w->charge_stage = 2;
	}

	ret = wacom_wez01_send(w, WEZ01_CMD_GARAGE_STATUS);
	if (ret)
		dev_warn(&w->client->dev,
			 "could not query S Pen charge state: %d\n", ret);
	mod_delayed_work(system_wq, &w->charge_work,
			 msecs_to_jiffies(WEZ01_CHARGE_STATUS_PERIOD_MS));
}

static bool wacom_wez01_handle_garage_reply(struct wacom_wez01 *w,
					    const u8 *data)
{
	u8 charge_state;

	if ((data[0] & 0x0f) != WEZ01_PKT_REPLY ||
	    data[1] != WEZ01_REPLY_GARAGE_CHARGE)
		return false;

	charge_state = data[2] & 0x0f;
	WRITE_ONCE(w->charge_status, wacom_wez01_charge_status(charge_state));
	dev_info(&w->client->dev,
		 "S Pen garage reply: docked=%u charge-state=%u\n",
		 READ_ONCE(w->docked), charge_state);
	wacom_wez01_notify_garage(w);
	return true;
}

static void wacom_wez01_set_docked(struct wacom_wez01 *w, bool docked)
{
	if (docked == READ_ONCE(w->docked))
		return;

	WRITE_ONCE(w->docked, docked);
	w->charge_stage = 0;
	if (!docked)
		WRITE_ONCE(w->charge_status, POWER_SUPPLY_STATUS_NOT_CHARGING);

	input_report_switch(w->input, SW_PEN_INSERTED, docked);
	input_sync(w->input);
	wacom_wez01_notify_garage(w);
	dev_info(&w->client->dev, "S Pen %s\n",
		 docked ? "docked" : "undocked");
	mod_delayed_work(system_wq, &w->charge_work, 0);
}

static bool wacom_wez01_handle_cover(struct wacom_wez01 *w, const u8 *data)
{
	bool closed;

	if ((data[0] & 0x0f) != WEZ01_PKT_NOTI ||
	    data[1] != WEZ01_NOTI_COVER_DETECT)
		return false;

	closed = data[3] & WEZ01_COVER_CLOSED;
	if (closed == READ_ONCE(w->cover_closed))
		return true;

	WRITE_ONCE(w->cover_closed, closed);
	/*
	 * SW_MACHINE_COVER is what the hardware means; SW_LID is the one
	 * logind and GNOME act on.  The gpio-keys hall keeps reporting SW_LID
	 * for plain covers, and the two never contradict each other because
	 * each answers a different lid.
	 */
	input_report_switch(w->input, SW_MACHINE_COVER, closed);
	input_report_switch(w->input, SW_LID, closed);
	input_sync(w->input);
	dev_info(&w->client->dev, "book cover %s\n",
		 closed ? "closed" : "open");

	return true;
}

static irqreturn_t wacom_wez01_pdct_irq(int irq, void *dev_id)
{
	struct wacom_wez01 *w = dev_id;

	wacom_wez01_set_docked(w, gpiod_get_value_cansleep(w->pdct) > 0);
	return IRQ_HANDLED;
}

static ssize_t pen_docked_show(struct device *dev,
			       struct device_attribute *attribute, char *buf)
{
	struct wacom_wez01 *w = dev_get_drvdata(dev);

	return sysfs_emit(buf, "%u\n", READ_ONCE(w->docked));
}
static DEVICE_ATTR_RO(pen_docked);

static ssize_t pen_charging_show(struct device *dev,
				 struct device_attribute *attribute, char *buf)
{
	struct wacom_wez01 *w = dev_get_drvdata(dev);
	const char *status = "unknown";

	switch (READ_ONCE(w->charge_status)) {
	case POWER_SUPPLY_STATUS_CHARGING:
		status = "charging";
		break;
	case POWER_SUPPLY_STATUS_FULL:
		status = "full";
		break;
	case POWER_SUPPLY_STATUS_NOT_CHARGING:
		status = "not-charging";
		break;
	}

	return sysfs_emit(buf, "%s\n", status);
}
static DEVICE_ATTR_RO(pen_charging);

static ssize_t pen_ble_reset_store(struct device *dev,
				   struct device_attribute *attribute,
				   const char *buf, size_t count)
{
	struct wacom_wez01 *w = dev_get_drvdata(dev);
	bool reset;
	int ret;

	ret = kstrtobool(buf, &reset);
	if (ret)
		return ret;
	if (!reset)
		return -EINVAL;
	if (!READ_ONCE(w->docked))
		return -ENODEV;

	/*
	 * RESET clears the pen's previous BLE bond and makes it advertise for a
	 * new host while it stays in the charging garage.  Keep it explicit:
	 * issuing it on every dock would destroy a valid bond.
	 */
	cancel_delayed_work_sync(&w->charge_work);
	ret = wacom_wez01_send(w, WEZ01_CMD_BLE_PAIR_RESET);
	if (ret) {
		mod_delayed_work(system_wq, &w->charge_work, 0);
		return ret;
	}

	w->charge_stage = 1;
	WRITE_ONCE(w->charge_status, POWER_SUPPLY_STATUS_CHARGING);
	wacom_wez01_notify_garage(w);
	mod_delayed_work(system_wq, &w->charge_work,
			 msecs_to_jiffies(WEZ01_CHARGE_START_DELAY_MS));
	dev_info(dev, "S Pen BLE pairing reset requested\n");

	return count;
}
static DEVICE_ATTR_WO(pen_ble_reset);

static struct attribute *wacom_wez01_attrs[] = {
	&dev_attr_pen_docked.attr,
	&dev_attr_pen_charging.attr,
	&dev_attr_pen_ble_reset.attr,
	NULL,
};

static const struct attribute_group wacom_wez01_group = {
	.attrs = wacom_wez01_attrs,
};

/*
 * Leave range transition: release the pen tool and clear the proximity flag
 * that gates touchscreen reporting.  Only the first caller out of the IRQ
 * thread and the silence timer actually emits the release events.
 */
static void wacom_wez01_leave_range(struct wacom_wez01 *w)
{
	if (atomic_cmpxchg(&wez01_pen_proximity, 1, 0) == 1) {
		if (w->prox) {
			input_report_abs(w->input, ABS_PRESSURE, 0);
			input_report_abs(w->input, ABS_DISTANCE, 0);
			input_report_key(w->input, BTN_TOUCH, 0);
			input_report_key(w->input, BTN_STYLUS, 0);
			input_report_key(w->input, BTN_TOOL_PEN, 0);
			input_report_key(w->input, BTN_TOOL_RUBBER, 0);
			input_sync(w->input);
			w->prox = false;
		}
	}
}

static void wacom_wez01_prox_timeout(struct timer_list *t)
{
	struct wacom_wez01 *w = timer_container_of(w, t, prox_timer);

	dev_dbg(&w->client->dev, "no pen report in %u ms; synthesising "
		"proximity out\n", WEZ01_PROXIMITY_TIMEOUT_MS);
	wacom_wez01_leave_range(w);
}

static irqreturn_t wacom_wez01_irq_handler(int irq, void *dev_id)
{
	struct wacom_wez01 *w = dev_id;
	u8 data[WEZ01_EVENT_SIZE + 1];
	int ret;

	ret = i2c_master_recv(w->client, data, sizeof(data));
	if (ret != sizeof(data))
		return IRQ_HANDLED;

	if (wacom_wez01_handle_garage_reply(w, data))
		return IRQ_HANDLED;

	if (wacom_wez01_handle_cover(w, data))
		return IRQ_HANDLED;

	if ((data[0] & 0x0f) != WEZ01_PKT_COORD)
		return IRQ_HANDLED;

	if (!(data[0] & WEZ01_RDY)) {
		timer_shutdown_sync(&w->prox_timer);
		wacom_wez01_leave_range(w);
		return IRQ_HANDLED;
	}

	input_report_key(w->input, BTN_TOOL_RUBBER, !!(data[0] & WEZ01_ERASER));
	input_report_key(w->input, BTN_TOOL_PEN, !(data[0] & WEZ01_ERASER));
	input_report_key(w->input, BTN_TOUCH, !!(data[0] & WEZ01_TIP));
	input_report_key(w->input, BTN_STYLUS, !!(data[0] & WEZ01_SIDE));
	/*
	 * The digitizer sits in the same orientation as the FTS sensor:
	 * invert-x + swap maps raw coordinates onto the landscape panel.
	 * Report native digitizer coordinates (100 units/mm); libinput
	 * maps them to the output using the resolution and physical size.
	 */
	{
		int px, py;

		px = get_unaligned_be16(&data[3]);
		py = w->max_x - get_unaligned_be16(&data[1]);
		px = clamp(px, pen_x_min, pen_x_max);
		py = clamp(py, pen_y_min, pen_y_max);
		input_report_abs(w->input, ABS_X, px);
		input_report_abs(w->input, ABS_Y, py);
	}
	input_report_abs(w->input, ABS_PRESSURE,
			 ((data[5] & 0x0f) << 8) | data[6]);
	input_report_abs(w->input, ABS_DISTANCE, data[7]);
	input_report_abs(w->input, ABS_TILT_X, (s8)data[8]);
	input_report_abs(w->input, ABS_TILT_Y, (s8)data[9]);
	input_sync(w->input);
	w->prox = true;
	atomic_set(&wez01_pen_proximity, 1);
	mod_timer(&w->prox_timer,
		  jiffies + msecs_to_jiffies(WEZ01_PROXIMITY_TIMEOUT_MS));

	return IRQ_HANDLED;
}

static void wacom_wez01_stop_timer(void *data)
{
	struct wacom_wez01 *w = data;

	timer_shutdown_sync(&w->prox_timer);
	wacom_wez01_leave_range(w);
}

static void wacom_wez01_cancel_charge_work(void *data)
{
	struct wacom_wez01 *w = data;

	cancel_delayed_work_sync(&w->charge_work);
}

static void wacom_wez01_clear_wake_irq(void *data)
{
	dev_pm_clear_wake_irq(data);
	device_init_wakeup(data, false);
}

static int wacom_wez01_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct power_supply_config supply_config = {};
	struct wacom_wez01 *w;
	struct input_dev *input;
	int pdct_irq;
	int ret;

	if (!i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
		return -ENODEV;

	if (!client->irq)
		return dev_err_probe(dev, -EINVAL, "no irq specified\n");

	w = devm_kzalloc(dev, sizeof(*w), GFP_KERNEL);
	if (!w)
		return -ENOMEM;

	w->client = client;
	i2c_set_clientdata(client, w);

	/*
	 * avdd is shared with the panel VCI rail; the enable is refcounted
	 * and the driver never power-cycles the pen.
	 */
	ret = devm_regulator_get_enable(dev, "avdd");
	if (ret)
		return dev_err_probe(dev, ret, "failed to enable avdd\n");

	/* high (plus a power cycle) selects the flash-mode bootloader */
	w->fwe = devm_gpiod_get(dev, "flash-mode", GPIOD_OUT_LOW);
	if (IS_ERR(w->fwe))
		return dev_err_probe(dev, PTR_ERR(w->fwe),
				     "failed to get flash-mode gpio\n");

	msleep(200);

	ret = wacom_wez01_query(w);
	if (ret) {
		dev_warn(dev, "query failed (%d), using default limits\n", ret);
		w->max_x = 14752;
		w->max_y = 23603;
		w->max_pressure = 4095;
		w->max_height = 255;
		w->max_tilt_x = 63;
		w->max_tilt_y = 63;
	}

	timer_setup(&w->prox_timer, wacom_wez01_prox_timeout, 0);

	w->pdct = devm_gpiod_get(dev, "pdct", GPIOD_IN);
	if (IS_ERR(w->pdct))
		return dev_err_probe(dev, PTR_ERR(w->pdct),
				     "failed to get S Pen dock detect gpio\n");
	w->docked = gpiod_get_value_cansleep(w->pdct) > 0;
	w->charge_status = w->docked ? POWER_SUPPLY_STATUS_UNKNOWN :
				       POWER_SUPPLY_STATUS_NOT_CHARGING;
	mutex_init(&w->command_lock);
	INIT_DELAYED_WORK(&w->charge_work, wacom_wez01_charge_work);

	input = devm_input_allocate_device(dev);
	if (!input)
		return -ENOMEM;

	w->input = input;
	input->name = "Wacom WEZ01 S Pen";
	input->id.bustype = BUS_I2C;
	/*
	 * libwacom matches integrated tablets on the i2c vendor/product IDs.
	 * With both left at zero it cannot match the S Pen entry and GNOME
	 * treats the pen as an external tablet, so its mapping does not follow
	 * the panel when the display rotates.
	 */
	input->id.vendor = 0x056a;	/* Wacom */

	input_set_capability(input, EV_KEY, BTN_TOUCH);
	input_set_capability(input, EV_KEY, BTN_STYLUS);
	input_set_capability(input, EV_KEY, BTN_TOOL_PEN);
	input_set_capability(input, EV_KEY, BTN_TOOL_RUBBER);
	input_set_capability(input, EV_SW, SW_PEN_INSERTED);
	input_set_capability(input, EV_SW, SW_MACHINE_COVER);
	input_set_capability(input, EV_SW, SW_LID);

	input_set_abs_params(input, ABS_X, 0, w->max_y, 0, 0);
	input_set_abs_params(input, ABS_Y, 0, w->max_x, 0, 0);
	input_set_abs_params(input, ABS_PRESSURE, 0, w->max_pressure, 0, 0);
	input_set_abs_params(input, ABS_DISTANCE, 0, w->max_height, 0, 0);
	input_set_abs_params(input, ABS_TILT_X, -w->max_tilt_x, w->max_tilt_x,
			     0, 0);
	input_set_abs_params(input, ABS_TILT_Y, -w->max_tilt_y, w->max_tilt_y,
			     0, 0);
	input_abs_set_res(input, ABS_X, WEZ01_RES_UNITS_PER_MM);
	input_abs_set_res(input, ABS_Y, WEZ01_RES_UNITS_PER_MM);

	__set_bit(INPUT_PROP_DIRECT, input->propbit);

	ret = input_register_device(input);
	if (ret)
		return dev_err_probe(dev, ret, "failed to register input\n");

	input_report_switch(input, SW_PEN_INSERTED, w->docked);
	input_sync(input);

	supply_config.drv_data = w;
	supply_config.fwnode = dev_fwnode(dev);
	w->pen_supply = devm_power_supply_register(dev, &wacom_wez01_pen_supply,
						   &supply_config);
	if (IS_ERR(w->pen_supply))
		return dev_err_probe(dev, PTR_ERR(w->pen_supply),
				     "failed to register S Pen power supply\n");

	ret = devm_device_add_group(dev, &wacom_wez01_group);
	if (ret)
		return dev_err_probe(dev, ret,
				     "failed to expose S Pen dock state\n");

	/*
	 * Register the teardown actions last so they run before the input
	 * device and power supply disappear when the driver is unbound.
	 */
	ret = devm_add_action_or_reset(dev, wacom_wez01_stop_timer, w);
	if (ret)
		return ret;
	ret = devm_add_action_or_reset(dev, wacom_wez01_cancel_charge_work, w);
	if (ret)
		return ret;

	ret = devm_request_threaded_irq(dev, client->irq, NULL,
					wacom_wez01_irq_handler, IRQF_ONESHOT,
					client->name, w);
	if (ret)
		return dev_err_probe(dev, ret, "failed to request irq\n");

	/*
	 * The keyboard folio's lid notifications arrive through Wacom, not
	 * GPIO107.  Keep the data IRQ able to wake the SoC so the open event
	 * can be read after resume; the IRQ is routed through the SM8550 PDC.
	 */
	ret = device_init_wakeup(dev, true);
	if (ret)
		return ret;
	ret = dev_pm_set_wake_irq(dev, client->irq);
	if (ret) {
		device_init_wakeup(dev, false);
		return dev_err_probe(dev, ret, "cannot configure lid wake IRQ\n");
	}
	ret = devm_add_action_or_reset(dev, wacom_wez01_clear_wake_irq, dev);
	if (ret)
		return ret;

	pdct_irq = gpiod_to_irq(w->pdct);
	if (pdct_irq < 0)
		return dev_err_probe(dev, pdct_irq,
				     "failed to map S Pen dock interrupt\n");
	w->pdct_irq = pdct_irq;
	ret = devm_request_threaded_irq(dev, pdct_irq, NULL,
					wacom_wez01_pdct_irq,
					IRQF_ONESHOT | IRQF_TRIGGER_RISING |
					IRQF_TRIGGER_FALLING,
					"wacom-wez01-dock", w);
	if (ret)
		return dev_err_probe(dev, ret,
				     "failed to request S Pen dock interrupt\n");

	wacom_wez01_send(w, WEZ01_COM_SAMPLERATE_START);
	if (w->docked)
		mod_delayed_work(system_wq, &w->charge_work, 0);

	return 0;
}

static int wacom_wez01_suspend(struct device *dev)
{
	struct wacom_wez01 *w = dev_get_drvdata(dev);

	disable_irq(w->pdct_irq);
	cancel_delayed_work_sync(&w->charge_work);
	timer_shutdown_sync(&w->prox_timer);
	wacom_wez01_leave_range(w);
	/*
	 * Keep the digitiser sampling and its data IRQ armed: the keyboard
	 * folio's lid notification that wakes the tablet is read from this
	 * IRQ.  The reference port runs deep sleep the same way.
	 */

	return 0;
}

static int wacom_wez01_resume(struct device *dev)
{
	struct wacom_wez01 *w = dev_get_drvdata(dev);

	wacom_wez01_send(w, WEZ01_COM_SURVEY_EXIT);
	wacom_wez01_send(w, WEZ01_COM_SAMPLERATE_START);
	enable_irq(w->pdct_irq);
	wacom_wez01_set_docked(w, gpiod_get_value_cansleep(w->pdct) > 0);
	if (READ_ONCE(w->docked))
		mod_delayed_work(system_wq, &w->charge_work, 0);

	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(wacom_wez01_pm_ops,
				wacom_wez01_suspend, wacom_wez01_resume);

static const struct of_device_id wacom_wez01_of_match[] = {
	{ .compatible = "wacom,w90xx" },
	{ }
};
MODULE_DEVICE_TABLE(of, wacom_wez01_of_match);

static const struct i2c_device_id wacom_wez01_id[] = {
	{ "wacom-wez01" },
	{ }
};
MODULE_DEVICE_TABLE(i2c, wacom_wez01_id);

static struct i2c_driver wacom_wez01_driver = {
	.driver = {
		.name = "wacom-wez01",
		.of_match_table = wacom_wez01_of_match,
		.pm = pm_sleep_ptr(&wacom_wez01_pm_ops),
		.probe_type = PROBE_PREFER_ASYNCHRONOUS,
	},
	.probe = wacom_wez01_probe,
	.id_table = wacom_wez01_id,
};
module_i2c_driver(wacom_wez01_driver);

MODULE_DESCRIPTION("Wacom WEZ01 EMR digitizer driver");
MODULE_LICENSE("GPL");