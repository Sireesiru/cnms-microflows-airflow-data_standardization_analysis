
#!/usr/bin/env python3
"""
segmentation_pipeline.py

Reads a standardized *.h5.nxs file, performs YOLO segmentation,
and writes:
    masks/<sample>_mask.png
    overlays/<sample>_overlay.png
    measurements/<sample>_measurements.csv
"""

import logging
from pathlib import Path
import cv2
import h5py
import numpy as np
import pandas as pd
from ultralytics import YOLO
from skimage.measure import label, regionprops
import json
import time


###############################################################################
# Configuration
###############################################################################

#DATA_DIR = Path("/home/cloud/Globus-Personal-Docker/data")
CONFIG_FILE = Path("/home/cloud/cnms-qr-sample-tracking-main/config.json")
PROJECT_CONFIG_FILE = Path("/home/cloud/cnms-qr-sample-tracking-main/project_config.json")

with open(CONFIG_FILE, "r") as f:
    config_data = json.load(f)

with open(PROJECT_CONFIG_FILE, "r") as f:
    project_data = json.load(f)

STAGING_ROOT = Path(config_data["pipeline"]["watch_directory"])
DESTINATION_FOLDER = project_data["transfer"]["destination_folder"]
DATA_DIR = STAGING_ROOT / DESTINATION_FOLDER

MODEL_PATH = "/home/cloud/microflow_sidpy_nomad_server/best_AFM.pt"
CONFIDENCE = 0.25


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
MODEL = None


def load_model(model_path):
    global MODEL
    if MODEL is None:
        logging.info("Loading YOLO model: %s", model_path)
        MODEL = YOLO(model_path)
    return MODEL


def normalize_uint8(arr):
    arr = arr.astype(np.float32)
    arr -= arr.min()
    if arr.max() > 0:
        arr /= arr.max()
    return (arr * 255).astype(np.uint8)
#def read_h5_image(fname):
#    pixel_nm = 1.0
#    with h5py.File(fname, "r") as f:
#        for k, v in f.attrs.items():
#            if "pixel" in k.lower():
#                try:
#                    pixel_nm = float(v)
#                except Exception:
#                    pass
#        if "/entry/data/data" in f:
#            img = f["/entry/data/data"][()]
#        else:
#            img = None
#            def visitor(name, obj):
#                nonlocal img
#                if isinstance(obj, h5py.Dataset) and obj.ndim == 2 and img is None:
#                    img = obj[()]
#            f.visititems(visitor)
#            if img is None:
#                raise RuntimeError("No 2D dataset found.")
#    if img.ndim != 2:
#        raise RuntimeError(f"Expected 2D image. Got {img.shape}")
#    return img, pixel_nm / 1000.0
#
def read_h5_image(fname):
    pixel_nm = 1.0
    img = None

    with h5py.File(fname, "r") as f:
        for k, v in f.attrs.items():
            if "pixel" in k.lower():
                try:
                    pixel_nm = float(v)
                    break
                except Exception:
                    pass
        # ----------------------------------------------------------
        # Preferred NeXus location
        # ----------------------------------------------------------
        if "/entry/data/data" in f:
            img = f["/entry/data/data"][()]
        else:
            def visitor(name, obj):
                nonlocal img
                if (img is None
                    and isinstance(obj, h5py.Dataset)
                    and obj.ndim == 2
                ):
                    logging.info("Using dataset: %s", name)
                    img = obj[()]
            f.visititems(visitor)
    if img is None:
        raise RuntimeError("No 2D image dataset found.")
    if img.ndim != 2:
        raise RuntimeError(f"Expected a 2D image but found {img.shape}")
    return img, pixel_nm / 1000.0

def read_metadata(h5_file):
    """
    Read instrument metadata from standardized HDF5.
    """
    with h5py.File(h5_file, "r") as f:
        md = f["entry/Measurement_Nexus"].attrs
        reader = md.get("instrument_reader", None)
        file_type = md.get("instrument_file_type", None)
        # Decode bytes if necessary
        if isinstance(reader, bytes):
            reader = reader.decode()
        if isinstance(file_type, bytes):
            file_type = file_type.decode()
    return reader, file_type

def run_segmentation(img, model, conf):
    gray = normalize_uint8(img)
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    result = model.predict(
        rgb,
        conf=conf,
        retina_masks=True,
        verbose=False
    )[0]

    if result.masks is None:
        return None, None, pd.DataFrame()

    masks = result.masks.data.cpu().numpy()
    combined = np.max(masks.astype(np.uint8), axis=0)
    h, w = gray.shape

    combined = cv2.resize(combined,(w, h),interpolation=cv2.INTER_NEAREST)

    overlay = cv2.addWeighted(
        cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR),
        1.0,
        np.stack([combined * 0,combined * 255,combined * 0],axis=-1),0.5,0)
    props = []
    for idx, m in enumerate(masks):
        m = cv2.resize(m.astype(np.uint8),(w, h),interpolation=cv2.INTER_NEAREST)
        _, m = cv2.threshold(m, 0.5, 1, cv2.THRESH_BINARY)

        for r in regionprops(label(m)):
            props.append({
                "Mask": idx,
                "Area_pixels": r.area,
                "Area_um2": None,
                "Perimeter_pixels": r.perimeter,
                "Perimeter_um": None,
                "Centroid_X": r.centroid[1],
                "Centroid_Y": r.centroid[0],
                "Major_axis": r.major_axis_length,
                "Minor_axis": r.minor_axis_length,
                "Orientation_deg": np.degrees(r.orientation),
                "Eccentricity": r.eccentricity,
                "Solidity": r.solidity,
                "Extent": r.extent,
                "Equivalent_diameter": r.equivalent_diameter})
    return combined, overlay, pd.DataFrame(props)

def save_outputs(mask,overlay,df,pixel_um,stem,outdir):
    masks_dir = outdir / "masks"
    overlays_dir = outdir / "overlays"
    meas_dir = outdir / "measurements"

    masks_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)
    meas_dir.mkdir(parents=True, exist_ok=True)

    if not df.empty:
        df["Area_um2"] = df["Area_pixels"] * pixel_um ** 2
        df["Perimeter_um"] = df["Perimeter_pixels"] * pixel_um

    cv2.imwrite(str(masks_dir / f"{stem}_mask.png"),mask * 255)
    cv2.imwrite(str(overlays_dir / f"{stem}_overlay.png"),overlay)
    df.to_csv(meas_dir / f"{stem}_measurements.csv",index=False)


def main():
    pipeline_start = time.perf_counter()

    logging.info("=" * 60)
    logging.info("SEGMENTATION PIPELINE START")
    logging.info("Project directory: %s", DATA_DIR)
    logging.info("=" * 60)

    # ---------------------------------------------------------
    # Load model
    # ---------------------------------------------------------
    model_start = time.perf_counter()
    model = load_model(MODEL_PATH)

    logging.info(
        "[TIMING] Model loading: %.2f sec",
        time.perf_counter() - model_start
    )

    # ---------------------------------------------------------
    # Find H5 files
    # ---------------------------------------------------------
    h5_files = sorted(DATA_DIR.glob("*.h5.nxs"))

    if not h5_files:
        logging.info("No HDF5 files found.")
        logging.info(
            "[TIMING] TOTAL SEGMENTATION TIME: %.2f sec",
            time.perf_counter() - pipeline_start
        )
        return

    logging.info("Found %d HDF5 files.", len(h5_files))

    processed = 0
    skipped = 0
    failed = 0

    # ---------------------------------------------------------
    # Process files
    # ---------------------------------------------------------
    for infile in h5_files:

        file_start = time.perf_counter()

        stem = infile.name.replace(".h5.nxs", "")

        mask_file = DATA_DIR / "masks" / f"{stem}_mask.png"
        overlay_file = DATA_DIR / "overlays" / f"{stem}_overlay.png"
        csv_file = DATA_DIR / "measurements" / f"{stem}_measurements.csv"

        # Skip if already processed
        if (
            mask_file.exists()
            and overlay_file.exists()
            and csv_file.exists()
        ):
            logging.info("Skipping %s (already processed)", infile.name)
            skipped += 1
            continue

        logging.info("Processing %s", infile.name)

        try:
            # Read metadata
            reader, file_type = read_metadata(infile)

            logging.info("Reader    : %s", reader)
            logging.info("File type : %s", file_type)

            # Skip unsupported file types
            if file_type not in [".gwy", ".ibw"]:
                logging.info(
                    "Skipping %s (No AI model available)",
                    infile.name
                )
                skipped += 1
                continue

            # Read image
            img, pixel_um = read_h5_image(infile)
            logging.info("Image shape : %s", img.shape)

            # Segmentation
            inference_start = time.perf_counter()

            mask, overlay, df = run_segmentation(
                img,
                model,
                CONFIDENCE
            )

            logging.info(
                "[TIMING] AI inference + measurements: %.2f sec",
                time.perf_counter() - inference_start
            )

            if mask is None:
                logging.warning(
                    "No objects detected in %s",
                    infile.name
                )
                processed += 1

                logging.info(
                    "[TIMING] %s completed in %.2f sec",
                    infile.name,
                    time.perf_counter() - file_start
                )
                continue

            # Save results
            save_outputs(
                mask,
                overlay,
                df,
                pixel_um,
                stem,
                DATA_DIR
            )

            processed += 1

            logging.info(
                "Finished %s (%d objects)",
                infile.name,
                len(df)
            )

            logging.info(
                "[TIMING] %s completed in %.2f sec",
                infile.name,
                time.perf_counter() - file_start
            )

        except Exception as e:
            failed += 1

            logging.exception(
                "Failed processing %s after %.2f sec: %s",
                infile.name,
                time.perf_counter() - file_start,
                e
            )

    # ---------------------------------------------------------
    # Final summary
    # ---------------------------------------------------------
    total_time = time.perf_counter() - pipeline_start

    logging.info("=" * 60)
    logging.info("SEGMENTATION PIPELINE SUMMARY")
    logging.info("Total files : %d", len(h5_files))
    logging.info("Processed   : %d", processed)
    logging.info("Skipped     : %d", skipped)
    logging.info("Failed      : %d", failed)
    logging.info(
        "[TIMING] TOTAL SEGMENTATION TIME: %.2f sec (%.2f min)",
        total_time,
        total_time / 60
    )
    logging.info("=" * 60)

if __name__ == "__main__":
    main()

#def main():
#    pipeline_start = time.perf_counter()
#    logging.info("=" * 60)
#    logging.info("SEGMENTATION PIPELINE START")
#    logging.info("Project directory: %s", DATA_DIR)
#    logging.info("=" * 60)
#    model_start = time.perf_counter()
#    model = load_model(MODEL_PATH)
#    logging.info("[TIMING] Model loading: %.2f sec",time.perf_counter() - model_start)
#
#def main():
#    logging.info("Starting segmentation pipeline")
#    model = load_model(MODEL_PATH)
#    h5_files = sorted(DATA_DIR.glob("*.h5.nxs"))
#
#    if not h5_files:
#        logging.info("No HDF5 files found.")
#        return
#    logging.info("Found %d HDF5 files.", len(h5_files))
#    processed = 0
#    skipped = 0
#
#    for infile in h5_files:
#
#        file_start = time.perf_counter()
#
#        stem = infile.name.replace(".h5.nxs", "")
#        mask_file = DATA_DIR / "masks" / f"{stem}_mask.png"
#        overlay_file = DATA_DIR / "overlays" / f"{stem}_overlay.png"
#        csv_file = DATA_DIR / "measurements" / f"{stem}_measurements.csv"
#
#        # Skip if already processed
#        if (mask_file.exists()
#            and overlay_file.exists()
#            and csv_file.exists()
#        ):
#            logging.info("Skipping %s (already processed)", infile.name)
#            skipped += 1
#            continue
#        logging.info("Processing %s", infile.name)
#
#        # Read metadata
#        reader, file_type = read_metadata(infile)
#
#        logging.info("Reader      : %s", reader)
#        logging.info("File type   : %s", file_type)
#
#        # Skip unsupported file types
#        #if reader != "GwyddionReader" or file_type != ".gwy":
#        if file_type not in [".gwy", ".ibw"]:
#            logging.info(
#                "Skipping %s (No AI model available)",
#                infile.name
#            )
#            skipped += 1
#            continue
#        try:
#
#            img, pixel_um = read_h5_image(infile)
#            logging.info("Image shape : %s", img.shape)
#            mask, overlay, df = run_segmentation(img,model,CONFIDENCE)
#
#            if mask is None:
#                logging.warning("No objects detected in %s",infile.name)
#                processed += 1
#                continue
#
#            save_outputs(mask,overlay,df,pixel_um,stem,DATA_DIR)
#            processed += 1
#            logging.info(
#                "Finished %s (%d objects)",
#                infile.name,
#                len(df)
#            )
#        except Exception as e:
#            logging.exception(
#                "Failed processing %s : %s",
#                infile.name,
#                e
#            )
#    logging.info("===================================")
#    logging.info("Segmentation Pipeline Summary")
#    logging.info("Total files : %d", len(h5_files))
#    logging.info("Processed   : %d", processed)
#    logging.info("Skipped     : %d", skipped)
#    logging.info("===================================")
#
#if __name__ == "__main__":
#    main()