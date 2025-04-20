#   Copyright (c) 2024, Signaloid.
#
#   Permission is hereby granted, free of charge, to any person obtaining a
#   copy of this software and associated documentation files (the "Software"),
#   to deal in the Software without restriction, including without limitation
#   the rights to use, copy, modify, merge, publish, distribute, sublicense,
#   and/or sell copies of the Software, and to permit persons to whom the
#   Software is furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#   FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#   DEALINGS IN THE SOFTWARE.

import argparse
import sys
import struct
import signal
import matplotlib.pyplot as plt
from c0microsd.interface import C0microSDSignaloidSoCInterface
from signaloid.distributional import DistributionalValue
from signaloid.distributional_information_plotting.plot_wrapper import plot

kSignaloidC0StatusWaitingForCommand = 0
kSignaloidC0StatusCalculating = 1
kSignaloidC0StatusDone = 2
kSignaloidC0StatusInvalidCommand = 3

kCalculateNoCommand = 0
kCalculateWeighted = 1

calculation_commands = {
    "weighted": kCalculateWeighted,
}

def sigint_handler(signal, frame):
    plt.close()
    sys.exit(0)

# Function to pack floats into a byte buffer
def pack_floats(floats: list, size: int) -> bytes:
    """
    Pack a list of floats to a zero-padded bytes buffer of length size

    :param doubles: List of doubles to be packed
    :param size: Size of target buffer

    :return: The padded bytes buffer
    """
    # Pack the number of floats as a uint32_t at the beginning
    buffer = struct.pack("<I", len(floats))
    # Pack the floats (each as a 4-byte float)
    buffer += struct.pack(f"<{len(floats)}f", *floats)

    # Pad the buffer with zeros
    if len(buffer) < size:
        buffer += bytes(size - len(buffer))
    elif len(buffer) > size:
        raise ValueError(
            f"Buffer length exceeds {size} bytes after packing floats."
        )
    return buffer


def unpack_floats(byte_buffer: bytes, count: int) -> list[int]:
    """
    This function unpacks 'count' number of single-precision floating-point
    numbers from the given byte buffer. It checks if the buffer has enough
    data to unpack.

    Parameters:
        byte_buffer: A bytes object containing the binary data.
        count: The number of single-precision floats (floats) to unpack.

    Returns:
        A list of unpacked double values.
    """

    # Each float (single-precision float) is 8 bytes
    float_size = 4

    # Check if the buffer has enough bytes to unpack the requested
    # number of doubles
    expected_size = float_size * count
    if len(byte_buffer) < expected_size:
        raise ValueError(
            f"Buffer too small: expected at least {expected_size} bytes, \
                got {len(byte_buffer)} bytes.")

    # Unpack the 'count' number of floats ('f' format for float in struct)
    format_string = f'{count}f'
    doubles = struct.unpack(format_string, byte_buffer[:expected_size])

    return list(doubles)
  
def parse_csv(csv_path: str) -> list[tuple[float, float, float]]:
    """
    Parses a CSV file containing accelerometer data into a list of tuples
    representing the X, Y, and Z axes.

    :param csv_path: Path to the CSV file.
    :return: List of tuples with (X, Y, Z) values.
    """
    import csv

    data = []
    with open(csv_path, 'r') as csvfile:
        csv_reader = csv.reader(csvfile)
        for row in csv_reader:
            if len(row) >= 3:
                x = float(row[0])
                y = float(row[1])
                z = float(row[2])
                data.append((x, y, z))
    return data

def parse_arguments():
    # Create the top-level parser
    parser = argparse.ArgumentParser(
        description='Host application for C0-microSD \
            accelerometer application'
    )

    parser.add_argument(
        'device_path',
        type=str,
        help='Path of C0-microSD',
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Subparser for "weighted" command (requires path to CSV)
    parser_add = subparsers.add_parser(
        'weighted',
        help='Get an array of weighted means from a CSV file with IMU data'
    )
    parser_add.add_argument('csv_path', type=str, help='Path to CSV file')
    parser_add.add_argument('--window-size', type=int, default=10, help='Window size (default: 10)')

    # Parse the arguments
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()

    # Handle the commands and their arguments
    if args.command == 'weighted':
        print(f"Getting weighted means from: {args.csv_path}")
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)

    C0_microSD = C0microSDSignaloidSoCInterface(args.device_path)

    # Register the signal handler for SIGINT
    signal.signal(signal.SIGINT, sigint_handler)

    try:
        C0_microSD.get_status()
        print(C0_microSD)

        if C0_microSD.configuration != "soc":
            raise RuntimeError(
                "Error: The C0-microSD is not in SoC mode. "
                "Switch to SoC mode and try again."
            )

        else:
            raw_values = parse_csv(args.csv_path)
            print(f"Read {len(raw_values)} rows from CSV file.")
            
            # TODO: Calculate the weighted means for each axis by creating a sliding window of size
            # Ensure that every window contains the same number of samples, so start the sliding window between 0 and window_size exclusive
            
            # TODO: Pack and send the windowed values to the device; record response from device
          
            # Parse inputs
            print("Sending parameters to C0-microSD...")

            C0_microSD.write_signaloid_soc_MOSI_buffer(
                pack_floats(
                    windowed_values,
                    C0_microSD.MOSI_BUFFER_SIZE_BYTES,
                )
            )

            # Calculate result
            result_buffer = C0_microSD.calculate_command(
                calculation_commands[args.command])

            # Interpret and remove the first 4 bytes as a float
            returned_weighted_mean = struct.unpack("f", result_buffer[:4])[0]
            
            # TODO: Append weighted mean to array for the axis currently being processed
            print(f"Received weighted mean: {returned_weighted_mean}")
    except Exception as e:
        print(
            f"An error occurred while calculating: \n{e} \nAborting.",
            file=sys.stderr
        )
