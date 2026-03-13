from db import SessionLocal, engine, Base
import datetime
import time
import random
import string
import os
import cv2
import numpy as np

# Import all CRUD functions
from app.services import (
    create_sensor_settings,
    create_work_config,
    create_dataset,
    create_dataset_image,
    create_trained_model,
    create_detection_result,
    create_generate_data,
    create_alignment_image,
    create_app_log
)
from app.env import DETECTION_RESULTS_FOLDER

# Utility Functions
def random_string(prefix: str, length: int = 6):
    return f"{prefix}_{''.join(random.choices(string.ascii_lowercase, k=length))}"

def create_random_image(path):
    width = random.randint(500, 1000)
    height = random.randint(500, 1000)
    # Random dominant color (BGR)
    color = [random.randint(0, 255) for _ in range(3)]
    # Create image
    img = np.full((height, width, 3), color, dtype=np.uint8)
    # Add noise
    noise = np.random.randint(-50, 50, (height, width, 3))
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    # Ensure dir exists
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Save
    cv2.imwrite(path, img)

# Data Generation Script
def generate_sample_data(base_time: datetime.datetime):
    db = SessionLocal()
    try:
        random_name = ''.join(chr(random.choice(list(range(65, 91)) + list(range(48, 58)))) for _ in range(4))# Random A-Z letter

        # Create Sensor Settings
        pattern_cols = random.randint(5, 15)
        pattern_rows = random.randint(5, 15)
        now = base_time.strftime("%Y%m%d-%H%M%S")
        sensor = create_sensor_settings(
            db,
            name=f"Sensor_{random_name}",
            intrinsic_path=f"/data/intrinsic_{random.randint(1, 9)}.json",
            perspective_path=f"/data/perspective_{now}.json",
            speed_path=f"/data/speed_{now}.csv",
            pattern_cols=pattern_cols,
            pattern_rows=pattern_rows,
            bias_path=None if random.random() < 0.2 else f"/data/bias_{random.randint(1, 9)}.json"
        )


        # Create Work Config
        use_roi=random.choice([True, False])
        if use_roi:
            roi=f"{random.randint(0,500)}x{random.randint(0,500)}-{random.randint(0,500)}x{random.randint(0,500)}"
        else:
            roi="0x0-0x0"
        sensor_filter=random.choice([0, 1, 2])
        if sensor_filter == 0:
            sensor_filter_threshold = None
        else:
            sensor_filter_threshold = random.randint(0, 100000)
        work_config = create_work_config(
            db,
            name=f"Config_{random_name}",
            sensor_setting_id=sensor.id,
            delta_t=random.randint(0, 100000),
            use_roi=use_roi,
            bias_path=f"/data/bias_{random.randint(1, 9)}.json",
            sensor_filter=sensor_filter,
            seg_kernel_size=random.choice(range(1, 36, 2)),
            seg_threshold=random.randint(0, 255),
            seg_padding=random.randint(0, 100),
            on_event_his_value=random.randint(-255, 255),
            off_event_his_value=random.randint(-255, 255),
            speed_correction_param=random.uniform(0.5, 1.5),
            colormap=random.choice(['JET', 'AUTUMN', 'BONE', 'HOT', 'RAINBOW']),
            roi=roi,
            sensor_filter_threshold=sensor_filter_threshold,
        )


        # # Create Alignment Image
        # create_alignment_image( #temp hist
        #     db,
        #     work_config_id=work_config.id,
        #     image_path=f"/data/align_images/t1-1/align_img_temp.png",
        #     alignment_coord=f"[{random.randint(0,500)},{random.randint(0,500)},{random.randint(0,500)},{random.randint(0,500)}]",
        #     image_index=0
        # )
        num_additional_images = random.randint(1, 3)
        for i in range(num_additional_images):
            create_alignment_image(
                db,
                work_config_id=work_config.id,
                image_path=f"/data/align_images/{work_config.name}/align_img_{i+1}.png",
                alignment_coord=f"[{random.randint(0,500)},{random.randint(0,500)},{random.randint(0,500)},{random.randint(0,500)}]",
                image_index=i
            )


        # Create Dataset
        dataset = create_dataset(
            db,
            name=f"Dataset_{random_name}",
            work_config_id=work_config.id,
            is_trained=random.choice([True, False])
        )


        # Create Dataset Image
        num_additional_images = random.randint(5, 10)
        for i in range(num_additional_images):
            # Add a random number of seconds to the current time
            additional_seconds = random.randint(0, 4)
            future_time = base_time + datetime.timedelta(seconds=additional_seconds)
            now = future_time.strftime("%Y%m%d-%H%M%S")
            dataset_image = create_dataset_image(
                db,
                dataset_id=dataset.id,
                image_source_path=f"/datasets/{work_config.id}/histogram/histogram_{now}.png",
                usage_type=random.choice(['OK', 'NG', 'OTHER']),
            )


        # Create Trained Model
        learn_method = random.choice([0, 1])
        trained_model = create_trained_model(
            db,
            name=f"Model_{random_name}",
            dataset_id=dataset.id,
            epochs=random.randint(5, 50),
            learn_method=learn_method,
            patch_size_1=random.randint(32, 128),
            input_size_1=random.randint(224, 512),
            weight_path_1=f"/datasets/{dataset.name}/{dataset.name}_{now}_1.pth",
            patch_size_2=random.randint(32, 128) if learn_method > 0.5 else None,  # Optional
            input_size_2=random.randint(224, 512) if learn_method > 0.5 else None,  # Optional
            weight_path_2=f"/datasets/{dataset.name}/{dataset.name}_{now}_2.pth" if learn_method else None  # Optional
        )


        # Create Detection Result
        for i in range(num_additional_images): #the same as dataset_image
            judgment = random.choice([0, 1])
            additional_seconds = random.randint(0, 4)
            future_time = base_time + datetime.timedelta(seconds=additional_seconds)

            date_folder = future_time.strftime("%Y%m%d")
            time_str = future_time.strftime("%Y%m%d-%H%M%S")

            # Define relative paths (relative to DETECTION_RESULTS_FOLDER)
            base_rel_dir = f"{work_config.id}/{date_folder}"

            if judgment == 0:
                his_rel_path = f"{base_rel_dir}/histograms/OK/histogram_{time_str}.png"
            else:
                his_rel_path = f"{base_rel_dir}/histograms/NG/histogram_{time_str}.png"

            thumb_rel_path = f"{base_rel_dir}/thumbnails/histogram_{time_str}.png"
            heat_rel_path = f"{base_rel_dir}/heatmaps/heatmap_{time_str}.png"

            # Create real images
            for rel_path in [his_rel_path, thumb_rel_path, heat_rel_path]:
                abs_path = os.path.join(DETECTION_RESULTS_FOLDER, rel_path)
                create_random_image(abs_path)

            detection_result = create_detection_result(
                db,
                work_config_id=work_config.id,
                trained_model_id=trained_model.id,
                judgment=judgment,
                thumbnail_path=thumb_rel_path,
                his_img_path=his_rel_path,
                heatmap_path=heat_rel_path
            )



        # Create Generate Data
        generated_data = create_generate_data(
            db,
            work_config_id=work_config.id,
            data_dir=f"/datasets/{work_config.id}/{dataset.name}/data.txt",
        )


        # Create App Log
        app_log = create_app_log(
            db,
            level="INFO",
            message=f"Sample {sensor.name} and {work_config.name} inserted successfully!",
            logger_name=f"generate_database_{random_name}"
        )

    except Exception as e:
        print("Error during generation:", e)
        db.rollback()
    finally:
        db.close()

import os
import subprocess
if __name__ == "__main__":
    # Simulate time differences between calls
    if not os.path.exists('db/dimmer.db'):
        process = subprocess.Popen("uv run alembic upgrade head", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.wait()
        # process = subprocess.Popen("uv run alembic downgrade -1", stdout=subprocess.PIPE, stderr=subprocess.PIPE) #TEST
        # process.wait()
    base_time = datetime.datetime.now()
    n_data = 30
    for i in range(n_data):
        time.sleep(0.5) #sleep because model has internal time
        offset_minutes = i * 5  # Each sample is 5 minutes apart
        simulated_time = base_time + datetime.timedelta(minutes=offset_minutes)
        generate_sample_data(simulated_time)
