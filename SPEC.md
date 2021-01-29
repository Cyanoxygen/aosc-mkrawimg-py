# Device Specification

Device specifications should be placed in `devices/` directory.

A device should have a defined path which consists of three identifiers: vendor, platform and device.

- The vendor ID is a shortened name of its manufacturer, or its own vendor name such as `sunxi` for Allwinner.
- The platform ID should reflect a series of devices which uses same generation or type of hardware platform.
- The device ID is a shortened device name given by manufacturer, or if you can't determine it, you can use its device codename like what Android does.
- All three IDs should be lowercase, and MUST follow this expression:
  ```
  [0-9a-z-_]*
  ```
- The full path of a device should be presented as `vendor/platform/device`.

For example, `rpi/rpi4/rpi-400` for Raspberry Pi 400, `rpi/rpi4/rpi-4b` for Raspberry Pi 4B which uses same platform as Raspberry Pi 400. As for the previous generation, `rpi/rpi3/rpi-3b-plus` for Raspberry 3B+.


