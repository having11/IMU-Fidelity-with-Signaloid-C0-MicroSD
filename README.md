[<img src="https://assets.signaloid.io/add-to-signaloid-cloud-logo-dark-v6.svg#gh-dark-mode-only" alt="[Add to signaloid.io]" height="30">](https://signaloid.io/repositories?connect=https://github.com/having11/IMU-Fidelity-with-Signaloid-C0-MicroSD#gh-dark-mode-only)
[<img src="https://assets.signaloid.io/add-to-signaloid-cloud-logo-light-v6.svg#gh-light-mode-only" alt="[Add to signaloid.io]" height="30">](https://signaloid.io/repositories?connect=https://github.com/having11/IMU-Fidelity-with-Signaloid-C0-MicroSD#gh-light-mode-only)

# IMU Fidelity with Signaloid C0 MicroSD

Folder `python-host-application/` contains the source code that runs on the host that communicates with Signaloid C0-microSD.
Folder `C0-microSD-application/` contains the source code, initialization assembly, and linker script for building an application for Signaloid C0-microSD.

## Cloning this repository

The correct way to clone this repository to get the hardware and firmware submodules is:

`git clone --recursive https://github.com/having11/IMU-Fidelity-with-Signaloid-C0-MicroSD`

To update all submodules:

`git pull --recurse-submodules`
`git submodule update --remote --recursive`

If you forgot to clone with `--recursive`, and end up with empty submodule directories, you can remedy this with

`git submodule update --init --recursive`

## How to use

### Flash the C0-microSD application

1. Navigate to the `signaloid-soc-application/` folder.
2. Modify the `DEVICE` flag in the `Makefile` to point to your C0-microSD device path.
3. Run `make flash` and `make switch` (the green LED should blink).
4. Power cycle the C0-microSD (the green LED should light up).

### Run the Python based host application

To run the python based host application you first need to install the Ux plotting dependencies. To do that:

1. Navigate to `python-host-application/`
2. Create a virtual environment: `python3 -m venv .env`
3. Activate virtual environment: `source .env/bin/activate`
4. Install the `signaloid-python` package: `pip install git+https://github.com/signaloid/signaloid-python`
5. Run the application: `cd ../ && sudo python3 python-host-application/host_application.py /dev/diskX weighted data/imu_data.csv"`, where `/dev/diskX` is the C0-microSD device path.

For more information regarding the different Signaloid C0-microSD operation modes refer to the official [documentation](https://c0-microsd-docs.signaloid.io/) page.

Once an output file is created, run

`cd python-host-application/ && python3 plot_imu_values.py`

to get a series of figures for the accelerations and positions across the 3 axes

## How to modify

If you choose to modify `src/main.c` in your own fork, follow these instructions for [setting up the repository in Signaloid's Developer Platform](https://docs.signaloid.io/docs/platform/getting-started/repositories/), then run

`cd submodules/C0-microSD-utilities/ && python -m src.python.signaloid_api.core_downloader --api-key YOUR_API_KEY --repo-id YOUR_REPO_ID`

which compiles and downloads a `.tar.gz` containing your new binary file to be flashed onto the C0-microSD.
