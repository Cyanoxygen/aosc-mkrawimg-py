# aosc-mkrawimg-ng

Rewrite of [aosc-mkrawimg](https://github.com/AOSC-Dev/aosc-mkrawimg).

A script used to generate ready to use AOSC OS images which can be flashed directly to a device, mostly for ARM devices.

## Usage

```
usage: ./aosc-mkrawimg [-h] [-v] [-f OSFILE] [-d WORKDIR] [-l LOGFILE] [-m MNTPREFIX] [-U] [-C] [-R]

An utility to geneate ready-to-flash AOSC OS images.

positional arguments:
  device                Target device to make an image for

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Enable debug output
  -f OSFILE, --osfile OSFILE
                        Specify an AOSC OS tarball
  -d WORKDIR, --workdir WORKDIR
                        Specify the work directory
  -l LOGFILE, --logfile LOGFILE
                        Specify where to place the log file
  -m MNTPREFIX, --mntprefix MNTPREFIX
                        Specify the prefix path of mount points
  -U, --noupdate        Skip the upgrade process after OS extraction
  -C, --nocleanup       Skip cleaning up the working directory
  -R, --norecreate      Skip the image creation, use the previously created image

```

## Configuration

You can easily modify `config.yml` to alter default configuration. View [CONFIGURATION.md](CONFIGURATION.md) for details.

## Device specification

Please follow [SPEC.md](SPEC.md) on how to write a Device specification suite.

## License

This program is licensed under GNU GPL v3.
