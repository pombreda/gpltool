#!/usr/bin/env python
#############################################################
# ubi_reader
# (c) 2013 Jason Pruitt (jrspruitt@gmail.com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#############################################################

import os
import sys
import time
import argparse

from modules import settings
from modules.ubi import ubi
from modules.ubi.defines import UBI_EC_HDR_MAGIC
from modules.ubifs import ubifs
from modules.ubifs.defines import UBIFS_NODE_MAGIC
from modules.utils import guess_filetype, guess_start_offset, guess_leb_size, guess_peb_size
from modules.ubi_io import ubi_file, leb_virtual_file


if __name__=='__main__':
    start = time.time()
    description = 'Show information about UBI or UBIFS image.'
    usage = 'display_info.py [options] filepath'
    parser = argparse.ArgumentParser(usage=usage, description=description)

    parser.add_argument('-l', '--log', action='store_true', dest='log',
                      help='Print extraction information to screen.')

    parser.add_argument('-v', '--verbose-log', action='store_true', dest='verbose',
                      help='Prints nearly everything about anything to screen.')

    parser.add_argument('-u', '--ubifs-info', action='store_true', dest='ubifs_info',
                      help='Get UBIFS information from inside a UBI image. (default: false)')
    
    parser.add_argument('-p', '--peb-size', type=int, dest='block_size',
                        help='Specify PEB size. (UBI Only)')
    
    parser.add_argument('-e', '--leb-size', type=int, dest='block_size',
                        help='Specify LEB size. (UBIFS Only)')

    parser.add_argument('-s', '--start-offset', type=int, dest='start_offset',
                        help='Specify offset of UBI/UBIFS data in file. (default: 0)')

    parser.add_argument('-n', '--end-offset', type=int, dest='end_offset',
                        help='Specify end offset of UBI/UBIFS data in file.')

    parser.add_argument('filepath', help='File to extract contents of.')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if args.filepath:
        path = args.filepath
        if not os.path.exists(path):
            parser.error("File path doesn't exist.")

    if args.start_offset:
        start_offset = args.start_offset
    else:
        start_offset = guess_start_offset(path)

    if args.end_offset:
        end_offset = args.end_offset
    else:
        end_offset = None

    filetype = guess_filetype(path, start_offset)
    if not filetype:
        parser.error('Could not determine file type.')

    settings.logging_on = args.log

    settings.logging_on_verbose = args.verbose

    ubifs_info = args.ubifs_info

    if args.block_size:
        block_size = args.block_size
    else:
        if filetype == UBI_EC_HDR_MAGIC:
            block_size = guess_peb_size(path)
        elif filetype == UBIFS_NODE_MAGIC:
            block_size = guess_leb_size(path)

        if not block_size:
            parser.error('Block size could not be determined.')


    # Create file object.
    ufile_obj = ubi_file(path, block_size, start_offset, end_offset)

    if filetype == UBI_EC_HDR_MAGIC:
        # Create UBI object
        ubi_obj = ubi(ufile_obj)

        # Display UBI info if not UBIFS request.
        if not ubifs_info:
            print ubi_obj.display()

        # Loop through found images in file.
        for image in ubi_obj.images:
            # Display image information if not UBIFS request.
            if not ubifs_info:
                print '%s' % image.display('\t')

            # Loop through volumes in each image.
            for volume in image.volumes:
                # Show UBI or UBIFS info.
                if not ubifs_info:

                    # Display volume information.
                    print image.volumes[volume].display('\t\t')

                else:
                    # Get blocks associated with this volume.
                    vol_blocks = image.volumes[volume].get_blocks(ubi_obj.blocks)
    
                    # Skip volume if empty.
                    if not len(vol_blocks):
                        continue
    
                    # Create LEB backed virtual file with volume blocks.
                    # Necessary to prevent having to load entire UBI image
                    # into memory.
                    lebv_file = leb_virtual_file(ubi_obj, vol_blocks)
    
                    # Create UBIFS object and print info.
                    ubifs_obj = ubifs(lebv_file)
                    print ubifs_obj.display()
                    print ubifs_obj.superblock_node.display('\t')
                    print ubifs_obj.master_node.display('\t')
                    print ubifs_obj.master_node2.display('\t')

    elif filetype == UBIFS_NODE_MAGIC:
        # Create UBIFS object
        ubifs_obj = ubifs(ufile_obj)
        print ubifs_obj.display()
        print ubifs_obj.superblock_node.display('\t')
        print ubifs_obj.master_node.display('\t')
        print ubifs_obj.master_node2.display('\t')

    else:
        print 'Something went wrong to get here.'