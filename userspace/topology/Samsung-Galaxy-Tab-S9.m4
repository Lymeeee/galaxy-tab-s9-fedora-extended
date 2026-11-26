# SPDX-License-Identifier: BSD-3-Clause
# AudioReach topology for Samsung Galaxy Tab S9 Wi-Fi (SM-X710 / SM8550).
#
# Provides both:
# - PRIMARY_MI2S_RX  (2-channel I2S, backwards-compatible with existing DTS)
# - PRIMARY_TDM_RX_0 (4-channel discrete TDM for 4x CS35L45 speakers)
# - VA_CODEC_DMA_TX_0 (internal DMIC capture)
# - DISPLAY_PORT_RX_0 (USB-C DisplayPort audio)
include(`audioreach/audioreach.m4')
include(`audioreach/stream-subgraph.m4')
include(`audioreach/device-subgraph.m4')
include(`util/route.m4')
include(`util/mixer.m4')
include(`audioreach/tokens.m4')

dnl Playback MultiMedia1 (2 or 4 channels for MI2S / 4-ch TDM speakers)
STREAM_SG_PCM_ADD(audioreach/subgraph-stream-vol-playback.m4, FRONTEND_DAI_MULTIMEDIA1,
	`S16_LE', 48000, 48000, 2, 4,
	0x00004001, 0x00004001, 0x00006001, `110000')
dnl Playback MultiMedia2
STREAM_SG_PCM_ADD(audioreach/subgraph-stream-vol-playback.m4, FRONTEND_DAI_MULTIMEDIA2,
	`S16_LE', 48000, 48000, 2, 4,
	0x00004002, 0x00004002, 0x00006010, `110000')
dnl Capture MultiMedia3
STREAM_SG_PCM_ADD(audioreach/subgraph-stream-capture.m4, FRONTEND_DAI_MULTIMEDIA3,
	`S16_LE', 48000, 48000, 1, 2,
	0x00004003, 0x00004003, 0x00006020, `110000')
dnl Capture MultiMedia4
STREAM_SG_PCM_ADD(audioreach/subgraph-stream-capture.m4, FRONTEND_DAI_MULTIMEDIA4,
	`S16_LE', 48000, 48000, 1, 2,
	0x00004004, 0x00004004, 0x00006030, `110000')
dnl Playback MultiMedia5
STREAM_SG_PCM_ADD(audioreach/subgraph-compress-stream-vol-playback.m4, FRONTEND_DAI_MULTIMEDIA5,
	`S16_LE', 48000, 48000, 2, 4,
	0x0000400a, 0x0000400a, 0x00006040, `110000')
dnl Playback MultiMedia6 - for DisplayPort RX 0
STREAM_SG_PCM_ADD(audioreach/subgraph-stream-vol-playback.m4, FRONTEND_DAI_MULTIMEDIA6,
	`S16_LE', 48000, 48000, 2, 2,
	0x0000400b, 0x0000400b, 0x000060A0, `110000')

dnl Primary MI2S Playback (2-channel legacy/fallback speaker path)
DEVICE_SG_ADD(audioreach/subgraph-device-i2s-playback.m4, `Primary', PRIMARY_MI2S_RX,
	`S16_LE', 48000, 48000, 2, 2,
	LPAIF_INTF_TYPE_LPAIF, I2S_INTF_TYPE_PRIMARY, SD_LINE_IDX_I2S_SD0, DATA_FORMAT_FIXED_POINT,
	0x00004006, 0x00004006, 0x00006060, `PRIMARY_MI2S_RX')

dnl Primary TDM0 Playback (4-channel discrete quad-speaker path)
DEVICE_SG_ADD(audioreach/subgraph-device-tdm-playback.m4, `Primary', PRIMARY_TDM_RX_0,
	`S16_LE', 48000, 48000, 4, 4,
	LPAIF_INTF_TYPE_LPAIF, 0, 0, DATA_FORMAT_FIXED_POINT,
	0x00004011, 0x00004011, 0x000060C0, `PRIMARY_TDM_RX_0')

dnl VA Capture (internal DMICs)
DEVICE_SG_ADD(audioreach/subgraph-device-codec-dma-capture.m4, `VA_CODEC_DMA_TX_0', VA_CODEC_DMA_TX_0,
	`S16_LE', 48000, 48000, 1, 2,
	LPAIF_INTF_TYPE_VA, CODEC_INTF_IDX_TX0, 0, DATA_FORMAT_FIXED_POINT,
	0x00004008, 0x00004008, 0x00006080)

dnl DisplayPort0 Playback
DEVICE_SG_ADD(audioreach/subgraph-device-display-port-playback.m4, `DISPLAY_PORT_RX_0', DISPLAY_PORT_RX_0,
	`S16_LE', 48000, 48000, 2, 2,
	0, 0, 0, DATA_FORMAT_FIXED_POINT,
	0x00004010, 0x00004010, 0x000060B0, `DISPLAY_PORT_RX_0')

STREAM_DEVICE_PLAYBACK_MIXER(PRIMARY_MI2S_RX, ``PRIMARY_MI2S_RX'', ``MultiMedia1'', ``MultiMedia2'', ``MultiMedia5'')
STREAM_DEVICE_PLAYBACK_MIXER(PRIMARY_TDM_RX_0, ``PRIMARY_TDM_RX_0'', ``MultiMedia1'', ``MultiMedia2'', ``MultiMedia5'')
STREAM_DEVICE_PLAYBACK_MIXER(DISPLAY_PORT_RX_0, ``DISPLAY_PORT_RX_0'', ``MultiMedia5'', ``MultiMedia6'')

STREAM_DEVICE_PLAYBACK_ROUTE(PRIMARY_MI2S_RX, ``PRIMARY_MI2S_RX Audio Mixer'', ``MultiMedia1, stream0.logger1'', ``MultiMedia2, stream1.logger1'', ``MultiMedia5, stream4.logger1'')
STREAM_DEVICE_PLAYBACK_ROUTE(PRIMARY_TDM_RX_0, ``PRIMARY_TDM_RX_0 Audio Mixer'', ``MultiMedia1, stream0.logger1'', ``MultiMedia2, stream1.logger1'', ``MultiMedia5, stream4.logger1'')
STREAM_DEVICE_PLAYBACK_ROUTE(DISPLAY_PORT_RX_0, ``DISPLAY_PORT_RX_0 Audio Mixer'', ``MultiMedia5, stream4.logger1'', ``MultiMedia6, stream5.logger1'')

STREAM_DEVICE_CAPTURE_MIXER(FRONTEND_DAI_MULTIMEDIA3, ``VA_CODEC_DMA_TX_0'')
STREAM_DEVICE_CAPTURE_MIXER(FRONTEND_DAI_MULTIMEDIA4, ``VA_CODEC_DMA_TX_0'')
STREAM_DEVICE_CAPTURE_ROUTE(FRONTEND_DAI_MULTIMEDIA3, ``MultiMedia3 Mixer'', ``VA_CODEC_DMA_TX_0, device110.logger1'')
STREAM_DEVICE_CAPTURE_ROUTE(FRONTEND_DAI_MULTIMEDIA4, ``MultiMedia4 Mixer'', ``VA_CODEC_DMA_TX_0, device110.logger1'')
