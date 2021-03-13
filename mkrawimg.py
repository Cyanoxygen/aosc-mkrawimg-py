#!/usr/bin/sudo /usr/bin/python3

import argparse
import logging
import os
from os.path import pardir
import platform
import subprocess
import sys
from typing import List
import yaml

VERSION = ('0', '1', '0')
AUTHORS = ['Cyanoxygen <cyanoxygen@aosc.io>']
LICENSE = 'GPLv3'
REPO = ''
# RESDIR: directory where these config files and devices file placed.
#         Default is $PWD, but can be changed if the main program file is separated with configs.
RESDIR = os.path.abspath('/usr/lib/aosc-mkrawimg-py/')

SARGS = [
    ['-v', '--verbose', 'Enable debug output', 'store_true', False],
    ['-U', '--noupdate', 'Skip the upgrade process after OS extraction', 'store_true', False],
    ['-C', '--nocleanup', 'Skip cleaning up the working directory', 'store_true', False],
    ['-R', '--norecreate', 'Skip the image creation, use the previously created image', 'store_true', False],
]
VARGS = [
    ['-f', '--osfile', 'Specify an AOSC OS tarball', 'store', 'aosc-os_base_arm64_latest.tar.xz', str],
    ['-d', '--workdir', 'Specify the work directory', 'store', '/var/cache/mkrawimg', str],
    ['-l', '--logfile', 'Specify where to place the log file', 'store', 'mkrawimg.log', str],
    ['-m', '--mntprefix', 'Specify the prefix path of mount points', 'store', '/mnt/mkrawimg', str],
    ['-V', '--variants', 'Specify the OS variant e.g. cinnamon', 'store', 'base', str],
]
allowed_vals = {
    'method': ['tarball', 'bootstrap'],
    'map': ['mbr', 'gpt'],
    'fs_req': ['vfat', 'ext4']
}
if __name__ == '__main__':
    if platform.system() != 'Linux':
        print('This is not a joke, please run the program in Linux!', file=sys.stderr)
        exit(1)

    # Enforce root user execution
    if os.getuid() != 0:
        print("Please run me as root, thanks. Exiting.", file=sys.stderr)
        exit(1)

# Get current directory
# May never used, use RESDIR instead.
PWD = os.path.abspath('.')
DEVICES = f'{PWD}/devices' if not os.path.exists(f'{RESDIR}/devices') else f'{RESDIR}/devices'
#
#   Logging configuration
#
# This section configures the logging module, sets up a logger with two outputs.
# One is the logfile, and the other is the console output.

LOGGER_FORMAT = '%(asctime)-23s | %(levelname)-8s | %(message)s'
logformatter = logging.Formatter(fmt=LOGGER_FORMAT)
consolehandler = logging.StreamHandler(sys.stdout)
consolehandler.setFormatter(logformatter)
filehandler = logging.FileHandler('/dev/null')
filehandler.setFormatter(logformatter)
logger = logging.getLogger('makeimg')
logger.setLevel('INFO')
logger.addHandler(consolehandler)
info = logger.info
debug = logger.debug
error = logger.error
warn = logger.warning
crit = logger.critical

#
#   Argparse configuration
#
# This section defines command line arguments user can specify.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog=sys.argv[0],
        description='An utility to generate ready-to-flash AOSC OS images.',
        epilog=f'(C) {", ".join(AUTHORS)}. This program is licensed under {LICENSE}. \
    For more information please refer to {REPO}.'
    )
    for arg in VARGS:
        parser.add_argument(arg[0], arg[1], help=arg[2], action=arg[3], default=arg[4], type=arg[5])
    for arg in SARGS:
        parser.add_argument(arg[0], arg[1], help=arg[2], action=arg[3], default=arg[4])
    parser.add_argument('device', help='Target device to make an image for')
    args = parser.parse_args()


#
#   Utility functions
#

def bailout(msg: str = ''):
    crit(f'A critical error occurred! {msg}')
    crit('Can not proceed. Bailing out.')
    sys.exit(1)


def exc(exe: list, path: str = None, inp: str = None, test: bool = True) -> subprocess.CompletedProcess:
    """
    Execution with subprocess.run()
    Returns a CompletedProcess object.
    Records stdout and stderr.
    """
    if test:
        info(f"Executing with subprocess.run {exe}, PWD={path}")
        return subprocess.run('true')
    debug(f'Executing with subprocess.run {exe}, PWD={path}')
    ret = subprocess.run(args=exe, cwd=path, input=inp, encoding='utf-8',
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    debug('stdout:')
    debug(f'=======')
    for i in ret.stdout.splitlines():
        debug(i)
    debug("stderr:")
    debug(f'=======')
    for i in ret.stderr.splitlines():
        debug(i)
    # TODO: record stdout and stderr into log file even it is not in verbose mode
    return ret


class loadable:
    def __init__(self):
        pass

    def load(self, spec: dict):
        """
        Load partition spec from a dict, using black magic.

        :param spec: dict to load
        :return: None
        """
        for key in spec:
            deftype = type(self.__getattribute__(key))
            keytype = type(spec[key])
            if keytype != deftype:
                warn(f'Invalid type {keytype} of key {key}. Using default value.')
                continue
            if key not in self.__dict__:
                warn(f'Unknown key "{key}" in configuration. It will be ignored.')
                continue
            self.__setattr__(key, spec[key])


#
#   The configuration class
#
class AppConfig:
    """
    Holds the default app configuration, and loads config.yml.
    This class holds the `general' section of config.yml.
    """

    class _OSConfig:
        """
        This class holds os-install section of config.yml.
        """

        def __init__(self):
            self.lang: str = str(os.environ['LANG']) if 'LANG' in os.environ else 'en_US.UTF-8'
            self.timezone: str = 'Asia/Shanghai'
            self.hostname: str = 'aosc-:variantname'
            self.createuser: bool = True
            self.username: str = 'aosc'
            self.password: str = 'anthon'
            self.fullname: str = 'AOSC OS Built-In User'
            self.groups: str = 'audio,video,tty,wheel,adm'
            self.nopasswd: bool = True
            self.method: str = 'tarball'
            self.bootstrap: list = ['base']

        def __format__(self, format_spec: str) -> str:
            return ''

    def __init__(self):
        self.workdir: str = '/var/cache/aosc-mkrawimg'
        self.mntprefix: str = '/mnt/mkrawimg'
        self.logfile: str = 'mkrawimg.log'
        self.noupgrade: bool = False
        self.nocleanup: bool = False
        self.norecreate: bool = False
        self.verbose: bool = False
        self.osfile: str = ''
        self.variant: str = 'base'

        self.OSConfig = self._OSConfig()

    def load_from_file(self):
        """
        Load a config.yml file.
        """
        confname = f'{RESDIR}/config.yml'
        if not os.path.isfile(confname):
            warn('Unable to find config.yml. Using default configuration.')
            return

        try:
            conffile = open(confname, 'r')
        except OSError as e:
            warn(f'Unable to open config.yml: {e.errno} {e.strerror}.')
            warn('Using default configuration.')
            return
        except Exception as e:
            warn(f'Unable to open config.yml: {e}. Using default configuration.')
            return
        conf = yaml.safe_load(conffile)

        # This is the real magic
        for key in conf['general']:
            deftype = type(self.__getattribute__(key))
            keytype = type(conf['general'][key])
            if keytype != deftype:
                warn(f'Invalid type {keytype} of key {key}. Using default value.')
                continue
            if key not in self.__dict__:
                warn(f'Unknown key "{key}" in configuration. It will be ignored.')
                continue
            self.__setattr__(key, conf['general'][key])
        # load OSConfig in the same way
        for key in conf['os-install']:
            deftype = type(self.OSConfig.__getattribute__(key))
            keytype = type(conf['os-install'][key])
            if keytype != deftype:
                warn(f'Invalid type {keytype} of key {key}. Using default value.')
                continue
            if key not in self.OSConfig.__dict__:
                warn(f'Unknown key "{key}" in configuration. It will be ignored.')
                continue
            self.OSConfig.__setattr__(key, conf['os-install'][key])

    def load_from_args(self):
        # This is the real magic, again
        for key in args.__dict__:
            self.__setattr__(key, args.__dict__[key])


Config: AppConfig = AppConfig()

class Environment:
    """
    Environment: Class to check system environment.

    It checks if the system meets the minimum requirements,
    e.g. loop device support, and filesystem tools suite, binfmt support,
    and QEMU static emulators to support binfmt.
    Checks are done during .check(), any unmet requirements will result in a immidiate bailout.
    """
    def __init__(self) -> None:
        self.supported_fs: list = ['vfat', 'ext4']
        self.arch: str = ''
        self.os: str = ''
        self.loop_support = False
        self.binfmt = False

    @staticmethod
    def check_supported_fs() -> list:
        """
        Check available filesystem
        """
        ret = []
        output = []
        output.extend(os.listdir('/usr/bin'))
        output.extend(os.listdir('/usr/sbin'))

        for item in output:
            if item[0:5] == 'mkfs.':
                ret.append(item[5:])
        return ret

    @staticmethod
    def check_arch() -> str:
        arch = platform.machine()
        return arch

    @staticmethod
    def check_binfmt() -> bool:
        supported = True
        try:
            with open('/proc/sys/fs/binfmt_misc/status') as f:
                supported = (f.read() == 'enabled\n')  # bool
        except (FileNotFoundError, OSError):
            supported = False
        if supported:
            if len(os.listdir('/proc/sys/fs/binfmt_misc/')) <= 2:
                # Restart binfmt first
                subprocess.run(['systemctl', 'restart', 'systemd-binfmt.service'])
                if len(os.listdir('/proc/sys/fs/binfmt_misc/')) > 2:
                    return
                warn('Your system supports binfmt, but no foreign architecture support is enabled.')
                warn('Please ensure you have qemu and qemu-user-static installed.')
                supported = False
        else:
            warn('Your system does not support binfmt_misc.')
            warn('You can only make OS images for same architecture of your machine.')
        return supported

    @staticmethod
    def check_loop() -> bool:
        loopdev = subprocess.getoutput('losetup -f')
        loop_support = ('/dev/loop' in loopdev)
        if not loop_support:
            error('It looks like there is no loop device support for your kernel.')
            error('We are trying to fix this by manually loading `loop\' kernel module.')
            ret = subprocess.call(['modprobe', 'loop'])
            if not ret:
                loop_support = True
            else:
                error('Oops, your system does not have loop device support which this tool requires.')
                loop_support = False
        return loop_support

    def check(self):
        self.loop_support = self.check_loop()
        if not self.loop_support:
            bailout('Requirement does not meet: loop device')
        self.supported_fs = self.check_supported_fs()
        if not set(self.supported_fs).issuperset(allowed_vals['fs_req']):
            error('Oops, please make sure e2fsprogs and dosfstools are installed and try again.')
            bailout(f'Missing basic filesystem support: {" and ".join(allowed_vals["fs_req"])}')
        self.arch = self.check_arch()
        self.binfmt = self.check_binfmt()


class Device(loadable):
    def __init__(self):
        """
        Loads a device configuration.
        Loads a default value of all possible options first, then call load().
        """
        super().__init__()
        self.arch: str = Env.arch
        self.id = 'x86_64-bios'
        self.platformid = 'x86_64-generic'
        self.platformname = 'Generic x86_64 machine'
        self.platformdesc = 'Image for Generic x86_64 machine'
        self.path = ['x86_64', 'generic', self.id]
        self.desc = 'Image for Legacy BIOS machines'


#
#   Device-related class
#
class Partition(loadable):
        """
        Defines a partition.
        """
        option_label = {
            'vfat': '-n',
            'ext4': '-L',
            'btrfs': '-L'
        }
        def __init__(self, parent: object):
            super().__init__()
            self.path: str = '/dev/loop0'
            self.num: int = 1
            self.name: str = 'aosc'
            self.size: int = -1
            self.type: str = '83'
            self.fs: str = 'ext4'
            self.mount: str = '/'
            self.bootable: bool = True
            self.mountopt: str = ''
            self.flash: False
            self.file: str = ''
            self.ready: bool = False
            self.image = parent

        def gen_plan(self):
            """
            Generate a sfdisk(8) script. One partition at a time.
            """
            TYPE_MBR = 'type=0x{}, '
            TYPE_GPT = 'type={}, '
            SIZE = 'size={0}MiB, '
            SIZEREST = ''
            BOOTABLE = 'bootable, '
            # sfdisk(8) input per partition
            plan = ''
            # Partition type
            if self.image.map == 'mbr':
                plan += TYPE_MBR.format(self.type)
            else:
                plan += TYPE_GPT.format(self.type)
            # Partition size
            if self.size > 0:
                plan += SIZE.format(self.size)
            else:
                plan += SIZEREST
            if self.bootable:
                plan += BOOTABLE
            return plan

        def make_fs(self):
            """
            Format a partition (making filesystems).

            :return: None
            :raise: OSError
            if called program returned non-zero.
            """
            if (not self.fs) or self.type == '05':
                # In case of an extended partition, there's no point to make an fs here.
                return
            if self.fs not in Env.supported_fs:
                crit(f'Filesystem {self.fs} is not supported in this system.')
                crit('Treating as an critical error.')
                raise OSError(f'Unsupported filesystem: {self.fs}.')
            exe = f'mkfs.{self.fs}'
            opts = [exe]
            if self.name:
                opts.extend([self.option_label.get(self.fs, '-L'), self.name])
            opts.extend([f'{self.path}p{self.num}'])
            res = exc(opts)
            if res.returncode != 0:
                raise OSError(f"Failed to make filesystem {self.fs} at {self.path}p{self.num}.")

        def make(self):
            """
            Function called by Image.make() after the plain image is make.
            """
            try:
                info(f'{self.__class__.__name__}: Making filesystem {self.num}...')
                self.make_fs()
            except OSError as e:
                crit(e)
                # Raise this to the Image.make() to fail.
                raise e


class Image(loadable):
    """
    Class repesents an image.
    To make an actual image, call make().
    """
    def __init__(self, device: Device):
        super().__init__()
        self.variant: str = 'base'
        self.loopdev: str = '/dev/loop0'
        self.imgpath: str = Config.workdir
        self.filename: str = 'aosc-os_amd64_base.img'
        self.size: int = 5120
        self.sector: int = 512
        self.start: int = 2048
        self.map: str = 'mbr'
        self.device = device
        self.parts: List[self.Partition] = []
    
    def gen_plan(self):
        """
        Generate sfdisk(8) input.
        """
        info(f"{self.__class__.__name__}: Applying partition map...")
        plan = []
        plan.append(f'label: {self.map}')
        for i in self.parts:
            plan.append(i.gen_plan())
        info(f'{self.__class__.__name__}: generated plan:\n{plan}')
        return '\n'.join(plan)

    def make(self):
        info(f'{self.__class__.__name__}: Creating an empty image...')
        exe = ['dd', 'if=/dev/zero', f'of={self.imgpath}/{self.filename}', 'bs=1MiB', f'count={self.size}']
        ret = exc(exe)
        if ret.returncode != 0:
            raise OSError('Failed to create an image.')
        for i in self.parts:
            info(f'Making partition {i.num}...')
            i.make()

        pass


Env: Environment = Environment()
Devices: List[Device] = []
DevPath: dict = {}

def LoadDevPath():
    def parse(path):
        pass

    pass

def main():
    global Config, Env, filehandler
    info(f'Welcome to aosc-mkrawimg v{".".join(VERSION)}!')
    info('Reading config file.')
    Config.load_from_file()
    Config.load_from_args()
    info('Checking environments.')
    Env.check()
    # Time to setup a logfile.
    try:
        filehandler = logging.FileHandler(Config.logfile)
    except:
        error("Failed to setup a logfile. Disabling logging into logfile.")
    # Switch to debug as soon as we can, if either command line or config has enabled it.
    # Now the config is loaded and the command line options are parsed,
    # we really need to do this now.
    # For debug purpose.
    if args.verbose or Config.verbose:
        logger.setLevel(logging.DEBUG)
        debug('DEBUG output enabled!')
        debug('Now your console output could be really messy ^o^')
    debug('Loaded command options:')
    for key in args.__dict__:
        debug(f'{key:<12}: {str(args.__dict__[key]):<}')
    debug('Loaded config:')
    for key in Config.__dict__:
        debug(f'{key:<12}: {Config.__dict__[key]:<}')
    for key in Config.OSConfig.__dict__:
        debug(f'{key:<12}: {str(Config.OSConfig.__dict__[key]):<}')


if __name__ == '__main__':
    main()
