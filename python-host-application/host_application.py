# Code derived from Signaloid's C0-microSD calculator example:
# https://github.com/signaloid/Signaloid-C0-microSD-Demo-Calculator

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
from dataclasses import dataclass
import csv
import matplotlib.pyplot as plt
from c0microsd.interface import C0microSDSignaloidSoCInterface


@dataclass
class AccelerometerValues:
    averaged_x: float
    averaged_y: float
    averaged_z: float
    weighted_mean_x: float
    weighted_mean_y: float
    weighted_mean_z: float


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
    # Pack the number of floats as a float at the beginning
    buffer = struct.pack("<f", float(len(floats)))
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


def compute_weighted_means(data: list[tuple[float, float, float]], window_size: int) -> list[AccelerometerValues]:
    """
    Computes weighted means for each axis from accelerometer CSV data.
    For each axis (X, Y, Z), it splits the samples into groups based on
    sliding window starting offsets 0 to window_size - 1. In each group, the
    weighted mean is computed with weights 1, 2, …, n (where n is the number
    of samples in that group). All groups are formed based on every sample at
    indices offset, offset+window_size, offset+2*window_size, etc.
    Note: If groups end up having different lengths, they are processed separately;
    the design assumes there are enough samples to form complete groups.

    Returns a flat list with the weighted means for X first, then Y, then Z.
    """
    if not data:
        return []

    # Separate the axes
    xs = [x for (x, _, _) in data]
    ys = [y for (_, y, _) in data]
    zs = [z for (_, _, z) in data]

    def compute_axis_weighted_means(axis_data: list[float], axis: str) -> list[float]:
        """
        Computes the weighted means for a single axis.
        """

        weighted = []

        sliding_window_start = 0
        sliding_window_end = window_size

        print("len(axis_data)=", len(axis_data))

        while sliding_window_end < len(axis_data):
            # Pack and send the windowed values to the device; record response from device
            windowed_values = axis_data[sliding_window_start:sliding_window_end]
            print("Sending parameters to C0-microSD...", windowed_values)

            C0_microSD.write_signaloid_soc_MOSI_buffer(
                pack_floats(
                    windowed_values,
                    C0_microSD.MOSI_BUFFER_SIZE_BYTES,
                )
            )
            
            print("Sent values to C0-microSD, waiting for result...")

            # Calculate result
            result_buffer = C0_microSD.calculate_command(
                calculation_commands[args.command])
            
            print("Received result from C0-microSD. result_buffer[:4]=", result_buffer[4:8])

            # Interpret and remove the first 4 bytes as a float
            returned_weighted_mean = struct.unpack("f", result_buffer[4:8])[0]

            # Append weighted mean to array for the axis currently being processed
            print(
                f"Received weighted mean: {returned_weighted_mean} for {axis} axis")

            weighted.append(returned_weighted_mean)

            sliding_window_start += 1
            sliding_window_end += 1

            print("Sliding window end=", sliding_window_end)

        return weighted

    def compute_axis_means(axis_data: list[float], axis: str) -> list[float]:
        """
        Computes the simple average for a given axis using a sliding window.
        """
        means = []
        start = 0
        while start + window_size <= len(axis_data):
            window = axis_data[start:start + window_size]
            avg = sum(window) / window_size
            print(
                f"Calculated average: {avg} for {axis} axis over window starting at index {start}")
            means.append(avg)
            start += 1
        return means

    average_x = compute_axis_means(xs, 'X')
    average_y = compute_axis_means(ys, 'Y')
    average_z = compute_axis_means(zs, 'Z')

    weighted_x = compute_axis_weighted_means(xs, 'X')
    weighted_y = compute_axis_weighted_means(ys, 'Y')
    weighted_z = compute_axis_weighted_means(zs, 'Z')

    n = min(
        len(average_x),
        len(average_y),
        len(average_z),
        len(weighted_x),
        len(weighted_y),
        len(weighted_z)
    )
    accelerometer_results = []
    for i in range(n):
        accelerometer_results.append(
            AccelerometerValues(
                averaged_x=average_x[i],
                averaged_y=average_y[i],
                averaged_z=average_z[i],
                weighted_mean_x=weighted_x[i],
                weighted_mean_y=weighted_y[i],
                weighted_mean_z=weighted_z[i]
            )
        )
    return accelerometer_results


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
    parser_add.add_argument('--window-size', type=int,
                            default=10, help='Window size (default: 10)')

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

            values = compute_weighted_means(raw_values, args.window_size)
            print("Weighted means calculation completed successfully.")

            # Re-read the full CSV to obtain gyroscope and magnetometer values.
            full_rows = []
            with open(args.csv_path, newline="") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    # Expecting at least 9 columns: accelerometer (0-2), gyroscope (3-5), magnetometer (6-8)
                    if len(row) >= 9:
                        full_rows.append(row)

            # Determine the output CSV file name
            output_csv = "output_results.csv"

            # Open the output CSV and write header and rows.
            with open(output_csv, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                # Write header: accelerometer averages and weighted means, plus gyroscope and magnetometer values.
                writer.writerow([
                    "averaged_x", "averaged_y", "averaged_z",
                    "weighted_mean_x", "weighted_mean_y", "weighted_mean_z",
                    "gyro_x", "gyro_y", "gyro_z",
                    "mag_x", "mag_y", "mag_z"
                ])

                # Number of computed entries from sliding window equals:
                # len(full_rows) - window_size + 1; computed values in 'values' follow the same count.
                # For each computed window result, use the middle row of the window to extract gyroscope and magnetometer values.
                for i, result in enumerate(values):
                    mid_index = i + args.window_size // 2
                    if mid_index < len(full_rows):
                        try:
                            gyro_x = float(full_rows[mid_index][3])
                            gyro_y = float(full_rows[mid_index][4])
                            gyro_z = float(full_rows[mid_index][5])
                            mag_x = float(full_rows[mid_index][6])
                            mag_y = float(full_rows[mid_index][7])
                            mag_z = float(full_rows[mid_index][8])
                        except ValueError as ve:
                            print(
                                f"Skipping row {mid_index} due to conversion error: {ve}")
                            continue

                        writer.writerow([
                            result.averaged_x, result.averaged_y, result.averaged_z,
                            result.weighted_mean_x, result.weighted_mean_y, result.weighted_mean_z,
                            gyro_x, gyro_y, gyro_z,
                            mag_x, mag_y, mag_z
                        ])
                    else:
                        print(
                            f"Warning: Not enough CSV rows to map window index {i}.")

    except Exception as e:
        print(
            f"An error occurred while calculating: \n{e} \nAborting.",
            file=sys.stderr
        )
