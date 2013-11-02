#!/usr/bin/env python
# ==========================================================================
#
# Copyright (C) 2012-2013 RidgeRun, LLC (http://www.ridgerun.com)
# All Rights Reserved.
#
# Authors: Jose Pablo Carballo <jose.carballo@ridgerun.com>
#          Diego Benavides <diego.benavides@ridgerun.com>
#
# The contents of this software are proprietary and confidential to RidgeRun,
# LLC.  No part of this program may be photocopied, reproduced or translated
# into another programming language without prior written consent of 
# RidgeRun, LLC.
#
# The installer tool objective is to provide several ways to deploy the
# firmware to the target board. 
#
# ==========================================================================

"""
The installer tool objective is to provide several ways to deploy the
firmware to the target board. Current methods are:

    - Attached board on communication port.
    - Deploy all the firmware to an SD card.
    - Create and SD card installer for flash memory.
    
Help output:
::
    usage: installer.py [-h] -m <mode> -f <mmap> --kernel-file <kernel_file> [-y]
                        [-v] [-q] [--dryrun] [-d <device>] [--image <image>]
                        [--image-size <imagesize_mb>] [--uflash <uflash>]
                        [--ubl-file <ubl_file>] [--uboot-file <uboot_file>]
                        [--uboot-entry-addr <uboot_entry_addr>]
                        [--uboot-load-addr <uboot_load_addr>]
                        [--uboot-bootargs <uboot_bootargs>] [--work-dir <workdir>]
                        [--rootfs <rootfs>]
    
    optional arguments:
      -h, --help            show this help message and exit
      -m <mode>, --mode <mode>
                            Installation mode: sdloopback
      -f <mmap>, --mmap-config-file <mmap>
                            Memory map config file
      --kernel-file <kernel_file>
                            Path to the Kernel Image file to be installed.
      -y, --assume-yes      Automatic 'yes' to prompts; run non-interactively
      -v, --verbose         Enable debug
      -q, --quiet           Be as quiet as possible
      --dryrun              Sets the dryrun mode On (shell commands will be
                            logged, but not executed)
      -d <device>, --device <device>
                            Device to install
      --image <image>       The filename of the image to create in workdir
      --image-size <imagesize_mb>
                            Size in MB of the image file to create (integer
                            number)
      --uflash <uflash>     Path to the uflash tool
      --ubl-file <ubl_file>
                            Path to the UBL file
      --uboot-file <uboot_file>
                            Path to the U-Boot file
      --uboot-entry-addr <uboot_entry_addr>
                            U-Boot entry address (decimal)
      --uboot-load-addr <uboot_load_addr>
                            U-Boot load address (decimal)
      --uboot-bootargs <uboot_bootargs>
                            U-Boot bootargs environment variable (passed to the
                            Linux kernel)
      --work-dir <workdir>  Directory to perform temporary operations
      --rootfs <rootfs>     Path to the rootfs that will be installed.
"""

# ==========================================================================
# Imports
# ==========================================================================

import os
import sys
import rrutils
import methods
import argparse

# ==========================================================================
# Global variables
# ==========================================================================

_args = []
_args_sd = []
_args_sd_img = []
_args_nand = []
_parser = None
_parser_sd = None
_parser_sd_img = None
_parser_nand = None
_subparsers = None
_logger  = None

# ==========================================================================
# Constants
# ==========================================================================

# Modes
MODE_SD = 'sd'
MODE_SD_IMG = 'sd-img'
MODE_NAND = 'nand'
MODE_LOOPBACK = 'loopback'

# Components
COMP_IPL = "ipl"
COMP_BOOTLOADER = "bootloader"
COMP_KERNEL = "kernel"
COMP_FS = "filesystem"
COMP_CMDLINE = "cmdline"
COMP_BOOTCMD = "bootcmd"

# ==========================================================================
# Logging
# ==========================================================================

def _init_logging():

    global _logger

    _program_name = os.path.basename(sys.argv[0])
    
    rrutils.logger.basic_config(verbose=True)
    _logger = rrutils.logger.get_global_logger(_program_name,
                                               level=rrutils.logger.INFO)

# ==========================================================================
# Functions
# ==========================================================================

def _clean_exit(code=0):
    if code != 0: _logger.error('Exiting with code %d' % code)
    exit(code)

def _abort_install():
    _logger.error('Installation aborted')
    _clean_exit(-1)

def _check_is_dir(dirname):
    if not os.path.isdir(dirname):
        _logger.error('Unable to find %s' % dirname)
        _clean_exit(-1)

def _check_is_file(filename):
    if not os.path.isfile(filename):
        _logger.error('Unable to find %s' % filename)
        _clean_exit(-1)

def _check_x_ok(filename):
    if not os.access(filename, os.X_OK):
        _logger.error('No execution permissions on %s' % filename)
        _clean_exit(-1)

def _check_is_int(val, arg):
    try:
        int(val)
    except ValueError:
        _logger.error('%s must be an integer (%s)' % (arg, val))
        _clean_exit(-1)
        
# ==========================================================================
# Command line arguments
# ==========================================================================

def _missing_arg_exit(arg):
    _parser.print_help()
    _logger.error('Argument %s is required' % arg)
    _clean_exit(-1)
    
def _parse_args():
    global _args
    global _parser
    global _subparsers
    _parser = argparse.ArgumentParser()
    _subparsers = _parser.add_subparsers(help="installation mode (--help available)",
                                         dest="mode")
    
    _parser.add_argument('-y', '--assume-yes',
                       help='Automatic \'yes\' to prompts; '
                       'runs non-interactively',
                       dest='interactive',
                       action='store_false',
                       default=True)
    
    _parser.add_argument('-v', '--verbose',
                       help='Enable debug',
                       dest='verbose',
                       action='store_true',
                       default=False)
    
    _parser.add_argument('-q', '--quiet',
                       help='Be as quiet as possible',
                       dest='quiet',
                       action='store_true',
                       default=False)
    
    _parser.add_argument('--dryrun',
                       help='Sets the dryrun mode On (shell commands will be '
                            'logged, but not executed)',
                       dest='dryrun',
                       action='store_true',
                       default=False)

def _parse_sd_img_args():
    global _parser_sd_img
    _parser_sd_img = _subparsers.add_parser(MODE_SD_IMG)
    
    _parser_sd_img.add_argument('--image',
                       help="The filename of the image to create in workdir",
                       metavar='<image>',
                       dest='image')
    
    _parser_sd_img.add_argument('--image-size',
                       help="Size in MB of the image file to create (integer" \
                       " number)",
                       metavar='<imagesize_mb>',
                       dest='imagesize_mb')

def _parse_sd_args():
    global _parser_sd
    _parser_sd = _subparsers.add_parser(MODE_SD)

    _parser_sd.add_argument('--mmap-file',
                       help='Memory map config file',
                       metavar='<mmap>',
                       dest='mmap_file')

    _parser_sd.add_argument('--device',
                       help="Device to install",
                       metavar='<device>',
                       dest='device',
                       required=True)
    
    _parser_sd.add_argument('--kernel-img',
                       help='Path to the Kernel Image file to be installed.',
                       metavar='<kernel_img>',
                       dest='kernel_img',
                       required=True)
    
    # MODE_SD and MODE_LOOPBACK - Required arguments
    
    _parser_sd.add_argument('--uflash',
                       help='Path to the uflash tool',
                       metavar='<uflash>',
                       dest='uflash_bin',
                       required=True)
    
    _parser_sd.add_argument('--ubl-file',
                       help='Path to the UBL file',
                       metavar='<ubl_file>',
                       dest='ubl_file',
                       required=True)
    
    _parser_sd.add_argument('--uboot-file',
                       help='Path to the U-Boot file',
                       metavar='<uboot_file>',
                       dest='uboot_file',
                       required=True)
    
    _parser_sd.add_argument('--uboot-entry-addr',
                       help='U-Boot entry address (decimal)',
                       metavar='<uboot_entry_addr>',
                       dest='uboot_entry_addr',
                       required=True)
    
    _parser_sd.add_argument('--uboot-load-addr',
                       help='U-Boot load address (decimal)',
                       metavar='<uboot_load_addr>',
                       dest='uboot_load_addr',
                       required=True)
    
    _parser_sd.add_argument('--uboot-bootargs',
                       help='U-Boot bootargs environment variable (passed to" \
                       " the Linux kernel)',
                       metavar='<uboot_bootargs>',
                       dest='uboot_bootargs',
                       required=True)
    
    _parser_sd.add_argument('--work-dir',
                       help='Directory to perform temporary operations',
                       metavar='<workdir>',
                       dest='workdir',
                       required=True)
    
    _parser_sd.add_argument('--rootfs',
                       help='Path to the rootfs that will be installed.',
                       metavar='<rootfs>',
                       dest='rootfs',
                       default=None)

def _parse_nand_args():
    global _parser_nand
    _parser_nand = _subparsers.add_parser(MODE_NAND)
    
    _parser_nand.add_argument('--mmap-file',
                       help='Memory map config file',
                       metavar='<mmap>',
                       dest='mmap_file')
    
    components = [COMP_IPL, COMP_BOOTLOADER, COMP_KERNEL, COMP_FS,
                    COMP_CMDLINE, COMP_BOOTCMD]
    components_help = ("Components: % s" %
                       ''.join('%s|' % comp for comp in components).rstrip("|"))
    _parser_nand.add_argument('--component',
                       help=components_help,
                       metavar='<mode>',
                       dest='installation_mode',
                       required=False,
                       choices=components)

def _check_args():
    global _args
    _args = _parser.parse_args()
    if _args.verbose:
        _logger.setLevel(rrutils.logger.DEBUG)
    if _args.quiet: # quiet has precedence over verbose
        _logger.setLevel(rrutils.logger.CRITICAL)
    
def _check_args_sd():    
    global _args_sd
    _args_sd = _parser_sd.parse_args()    
    _check_is_file(_args_sd.mmap_file)
    _check_is_file(_args_sd.uflash_bin)
    _check_x_ok(_args_sd.uflash_bin)
    _check_is_file(_args_sd.ubl_file)
    _check_is_file(_args_sd.uboot_file)
    _check_is_dir(_args_sd.workdir)
    if _args_sd.rootfs:
        _check_is_dir(_args_sd.rootfs)
    
def _check_args_sd_img():
    global _args_sd_img
    _args_sd_img = _parser_sd_img.parse_args()
    _check_is_file(_args_sd_img.mmap_file)
    _check_is_file(_args_sd_img.uflash_bin)
    _check_x_ok(_args_sd_img.uflash_bin)
    _check_is_file(_args_sd_img.ubl_file)
    _check_is_file(_args_sd_img.uboot_file)
    _check_is_dir(_args_sd_img.workdir)
    if _args.rootfs:
        _check_is_dir(_args.rootfs)
    _check_is_int(_args.imagesize_mb, '--image-size')

# ==========================================================================
# Main logic
# ==========================================================================

def main():

    _init_logging()
    _parse_args()
    _parse_nand_args()
    _parse_sd_args()
    _parse_sd_img_args()
    _check_args()
    
    mode = _args.mode
    
    if mode == MODE_SD or mode == MODE_LOOPBACK:
        
        # Components installer
        
        comp_installer = methods.sdcard.ComponentInstaller()
        comp_installer.uflash_bin = _args.uflash_bin
        comp_installer.ubl_file =_args.ubl_file
        comp_installer.uboot_file = _args.uboot_file
        comp_installer.uboot_entry_addr = _args.uboot_entry_addr
        comp_installer.uboot_load_addr = _args.uboot_load_addr
        comp_installer.bootargs = _args.uboot_bootargs
        comp_installer.kernel_image = _args.kernel_img
        comp_installer.rootfs = _args.rootfs
        comp_installer.workdir = _args.workdir
        
        # SDCard installer
    
        sd_installer = methods.sdcard.SDCardInstaller(comp_installer)
        sd_installer.interactive = _args.interactive
        sd_installer.dryrun = _args.dryrun
        
        ret = sd_installer.read_partitions(_args.mmap_file)
        if ret is False: _abort_install()
        
        # Operations
        
        if mode == MODE_SD:
            sd_installer.device = _args.device
            sd_installer.mode = sd_installer.MODE_SD
            ret = sd_installer.format_sd()
            if ret is False: _abort_install()
        elif mode == MODE_LOOPBACK:
            sd_installer.mode = sd_installer.MODE_LOOPBACK
            ret = sd_installer.format_loopdevice(_args.workdir +
                                                 _args.image, 
                                                 _args.imagesize_mb)
            if ret is False: _abort_install()
        
        ret = sd_installer.mount_partitions(_args.workdir)
        if ret is False: _abort_install()
        
        ret = sd_installer.install_components()
        if ret is False: _abort_install()
        
        ret = sd_installer.release_device()
        if ret is False: _abort_install()
        
    if mode == MODE_NAND:
        pass
            
    _logger.info('Installation complete')
    _clean_exit(0)
    
if __name__ == '__main__':
    main()
