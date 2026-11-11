/* SPDX-License-Identifier: MIT
 *
 * libhardware_legacy.so replacement for the SPU daemons running under Fedora.
 *
 * spdaemon links libhardware_legacy only for the Android wake-lock API.  The
 * real library (even the VNDK 33 build) pulls in libbinder, libhidlbase and
 * the suspend HAL, none of which this runtime provides, so the daemon spins
 * before it opens /dev/vndbinder.  Export only the two wake-lock entry points
 * and let the port's own power management decide when the tablet sleeps.
 */

int acquire_wake_lock(int lock, const char *id)
{
	(void)lock;
	(void)id;
	return 0;
}

int release_wake_lock(const char *id)
{
	(void)id;
	return 0;
}
