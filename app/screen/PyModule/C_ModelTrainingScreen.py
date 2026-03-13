"""Model training screen module for Kivy-based application.

This module defines the ModelTrainingScreen class, which manages the user interface
and logic for starting, monitoring, and controlling model training sessions.
It integrates database models, process management, and UI updates.
"""
import os
import re
import time
import threading
import traceback
import subprocess
import psutil
from datetime import datetime
from threading import RLock
from contextlib import contextmanager

from kivy.app import App
from kivy.clock import Clock
from kivy.logger import Logger

from sqlalchemy import func

from app.env import BE_FOLDER, DATASETS_FOLDER, FAST_FLOW_BACKBONE, PYTHON_RUNNER
from app.libs.constants.colors import COLORS
from app.libs.widgets.components import MyPopup, FormScreen

from db.models.datasets import Datasets
from db.models.system_config import SystemConfig
from db.models.trained_models import TrainedModels
from db.session import get_db

class LearnMethod:
    """Constants for model training learning methods."""
    PATCH = "0"
    PARALLEL = "1"


class ModelTrainingScreen(FormScreen):  # pylint: disable=too-many-instance-attributes
    """
    Screen C2: Model Training Screen.

    Manages the AI model training process including:
    - Training parameter configuration (epochs, patch size, input size, etc.)
    - Training execution and monitoring
    - Training log display and progress tracking
    - Training state management (running, completed, stopped)
    - Database integration for trained models

    This class requires many instance attributes to manage the complex training
    workflow, UI state, threading, and process management.
    """

    def set_left_mouse_disabled(self, disabled: bool):
        """Enable/disable left mouse functionality"""
        blockers = self.find_all_blockers()
        for blocker in blockers:
            if disabled:
                blocker.active = True
            else:
                blocker.active = False
        self.ids.c2_epoch_input.allow_hover = not disabled

    def find_all_blockers(self):
        """Find all LocalTouchBlocker widgets in the widget tree.

        Recursively walks through the widget hierarchy starting from this screen
        to find all LocalTouchBlocker instances.

        Returns:
            list: A list of all LocalTouchBlocker widgets found in the tree.
        """
        blockers = []

        def walk_widget(widget):
            if widget.__class__.__name__ == 'LocalTouchBlocker':
                blockers.append(widget)
            for child in widget.children:
                walk_widget(child)
        walk_widget(self)
        return blockers

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        # Use RLock to prevent deadlocks
        self._training_lock = RLock()
        self._ui_lock = RLock()

        self.popup = MyPopup()
        self.current_epoch = 0
        self.total_epochs = 0
        self.has_completed_epochs = False

        self._training_thread = None
        self._training_completed = False
        self._result_viewed = False

        self._screen_active = False
        self._pending_result_view = None
        self._spinner_selections = {}
        self._training_process = None
        self._training_stopped = False

    def start_log_thread(self, validation_result):
        """Start logging thread for training process"""
        if self._is_training_running():
            return
        self.clear_errors()

        def run():
            try:
                # Mark training as started and disable button
                self._training_completed = False
                self._result_viewed = False
                self._training_stopped = False

                Clock.schedule_once(
                    lambda dt: self._update_training_button_state(), 0.1)
                # Get training parameters and setup database in single transaction
                training_params = self._prepare_training_data()
                if not training_params:
                    return

                weight_folder = training_params.get('weight_folder')

                self._cleanup_existing_weights(weight_folder)

                # Execute training command
                self._execute_training_command(training_params)
            except Exception:
                traceback.print_exc()
                pass # pylint: disable=unnecessary-pass
            finally:
                # Mark training as completed and re-enable button
                if validation_result and validation_result['is_valid'] and not self._training_stopped:
                    self._training_completed = True
                Clock.schedule_once(
                    lambda dt: self._update_training_button_state(), 0.1)
                Clock.schedule_once(
                    lambda dt: self.set_left_mouse_disabled(False), 0)

                # Clean up process reference
                self._training_process = None

        self._training_thread = threading.Thread(target=run, daemon=True)
        self._training_thread.start()

    def _is_training_running(self):
        """Check if training thread is currently running"""
        return (self._training_thread is not None and
                self._training_thread.is_alive())

    def _is_training_completed_but_not_viewed(self):
        """Check if training completed but user hasn't viewed results yet"""
        return (self._training_completed and
                not self._result_viewed and
                (self._training_thread is None or not self._training_thread.is_alive()))

    def _mark_result_as_viewed(self):
        """Mark that user has viewed the training results"""
        self._result_viewed = True
        # Update button state when result is viewed
        Clock.schedule_once(
            lambda dt: self._update_training_button_state(), 0.1)

    def _should_reset_screen(self):
        """Determine if screen should be reset based on training state"""
        # Case 3: Training completed and user has viewed results
        if (self._training_completed and self._result_viewed):
            # Reset flags for next training session
            self._training_completed = False
            self._result_viewed = False
            self._training_thread = None
            return True

        # Case 1: Training is running - don't reset
        if self._is_training_running():
            return False

        # Case 2: Training completed but not viewed yet - don't reset
        if self._is_training_completed_but_not_viewed():
            return False

        # Default case: reset screen
        return True

    def _update_training_button_state(self):
        """Update training button text and disabled state based on training status"""
        try:
            training_button = self.ids.training_button
            stop_training_button = self.ids.stop_training_button
            if self._is_training_running():
                # Training is running - disable button
                training_button.disabled = True
                training_button.enable_hover = False
                stop_training_button.disabled = False
                stop_training_button.enable_hover = True

            elif self._is_training_completed_but_not_viewed():
                # Training completed but not viewed - keep disabled
                training_button.disabled = True
                training_button.enable_hover = False
                stop_training_button.disabled = True
                stop_training_button.enable_hover = False
            else:
                # Training not running or completed and viewed - enable button
                training_button.disabled = False
                training_button.enable_hover = True
                stop_training_button.disabled = True
                stop_training_button.enable_hover = False
        except (AttributeError, KeyError):
            traceback.print_exc()

    def _cleanup_existing_weights(self, folder_path):
        """Remove all .pth weight files in the given folder before starting new training"""
        try:
            if os.path.isdir(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.endswith('.pth') or filename.endswith('.engine') or filename.endswith('.onnx'):
                        file_path = os.path.join(folder_path, filename)
                        try:
                            os.remove(file_path)
                            print(f"Removed weight file: {file_path}")
                        except OSError:
                            traceback.print_exc()
        except Exception:
            traceback.print_exc()

    def _validate_training_inputs(self):
        """Validate all training input fields"""
        model_name = self.ids.c2_model_name_input.text
        dataset_name = self.ids.c2_dataset_select.text
        epochs = self.ids.c2_epoch_input.text

        show_log = None
        training_status_placeholder = False

        def set_default_log_if_needed():
            nonlocal show_log, training_status_placeholder
            if not show_log:
                show_log = (
                    'training_status_placeholder_C2',
                    [1, 1, 1, 1]
                )
                training_status_placeholder = True

        self.ids.c2_model_name_input.validate_text(model_name)
        if self.ids.c2_model_name_input.error_message:
            set_default_log_if_needed()
        else:
            self.ids.c2_model_name_input.validate_filename(model_name)
            if self.ids.c2_model_name_input.error_message:
                set_default_log_if_needed()

        validations = [
            (self.ids.c2_dataset_select, dataset_name, 'validate_text'),
            (self.ids.c2_epoch_input, epochs, 'validate_text')
        ]

        for field, value, method_name in validations:
            getattr(field, method_name)(value)
            if field.error_message:
                set_default_log_if_needed()
        return {
            'is_valid': not self.ids.c2_model_name_input.error_message and not self.ids.c2_dataset_select.error_message and not self.ids.c2_epoch_input.error_message,
            'errors': self.ids.c2_model_name_input.error_message or self.ids.c2_dataset_select.error_message or self.ids.c2_epoch_input.error_message,
            'show_log': show_log,
            'training_status_placeholder': training_status_placeholder
        }

    def _handle_validation_errors(self, errors, show_log, training_status_placeholder):
        """Handle validation errors by displaying them in UI"""
        if show_log:
            text_key = show_log[0]
            color = show_log[1]
            if training_status_placeholder:
                Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                    text_key=text_key,
                    color=color,
                ))
            else:
                Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                    text_key=text_key,
                    color=color
                ))

        if errors:
            def show_popup(dt):
                failure_popup = self.popup.create_adaptive_popup(
                    title='error_popup',
                    message='error_training_popup_C2'
                )
                failure_popup.open()

            Clock.schedule_once(show_popup, 0)

    def _prepare_training_data(self):
        """Get training parameters and setup database records in single transaction"""
        try:
            model_name = self.ids.c2_model_name_input.text
            dataset_name = self.ids.c2_dataset_select.text
            epochs = self.ids.c2_epoch_input.text

            with get_db() as db:
                # Get dataset and work_config_id
                dataset = db.query(Datasets) \
                    .filter(Datasets.name == dataset_name) \
                    .filter(Datasets.deleted_at.is_(None)) \
                    .first()

                if not dataset:
                    Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                        text_key='error_training_log_C2',
                        color=COLORS['LIGHT_RED'],
                    ))
                    return None

                work_config_id = dataset.work_config_id
                if not work_config_id:
                    Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                        text_key='error_training_log_C2',
                        color=COLORS['LIGHT_RED'],
                    ))
                    return None

                # Prepare training parameters
                learn_method = LearnMethod.PATCH \
                    if self.ids.c2_training_method_select.text == self.app.lang.get('learn_method_1') \
                    else LearnMethod.PARALLEL
                m1_input_size = self.ids.input_size_1_select.ids.spinner.text
                m1_patch_size = self.ids.patch_size_1_select.ids.spinner.text
                m1_weight_path = os.path.join(
                    DATASETS_FOLDER,
                    str(work_config_id),
                    dataset_name,
                    model_name,
                    'weights',
                    fr'm1_{FAST_FLOW_BACKBONE}_patch-{m1_patch_size}_input-{m1_input_size}.pth'
                )

                m1_engine_path = os.path.join(
                    DATASETS_FOLDER,
                    str(work_config_id),
                    dataset_name,
                    model_name,
                    'weights',
                    fr'm1_{FAST_FLOW_BACKBONE}_patch-{m1_patch_size}_input-{m1_input_size}.engine'
                )

                m2_input_size = None
                m2_patch_size = None
                m2_weight_path = None
                m2_engine_path = None

                if str(learn_method) == LearnMethod.PARALLEL:
                    m2_input_size = self.ids.input_size_2_select.ids.spinner.text
                    m2_patch_size = self.ids.patch_size_2_select.ids.spinner.text
                    m2_weight_path = os.path.join(
                        DATASETS_FOLDER,
                        str(work_config_id),
                        dataset_name,
                        model_name,
                        'weights',
                        fr'm2_{FAST_FLOW_BACKBONE}_patch_{m2_patch_size}_input_{m2_input_size}.pth'
                    )

                    m2_engine_path = os.path.join(
                        DATASETS_FOLDER,
                        str(work_config_id),
                        dataset_name,
                        model_name,
                        'weights',
                        fr'm2_{FAST_FLOW_BACKBONE}_patch_{m2_patch_size}_input_{m2_input_size}.engine'
                    )

                # Prepare data_root
                data_root = os.path.join(DATASETS_FOLDER, str(
                    work_config_id), dataset_name, 'data.txt')

                # Calculate weight_folder
                weight_folder = os.path.dirname(m1_weight_path)

                return {
                    'model_name': model_name,
                    'dataset_id': dataset.id,
                    'dataset_name': dataset_name,
                    'epochs': epochs,
                    'work_config_id': work_config_id,
                    'learn_method': learn_method,
                    'm1_input_size': m1_input_size,
                    'm1_patch_size': m1_patch_size,
                    'm1_weight_path': m1_weight_path,
                    'm1_engine_path': m1_engine_path,
                    'm2_input_size': m2_input_size,
                    'm2_patch_size': m2_patch_size,
                    'm2_weight_path': m2_weight_path,
                    'm2_engine_path': m2_engine_path,
                    'data_root': data_root,
                    'weight_folder': weight_folder
                }

        except Exception:
            Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                text_key='error_training_log_C2',
                color=COLORS['LIGHT_RED'],
            ))
            traceback.print_exc()
            return None

    def _update_existing_model(self, existing_model, params):
        """Update existing model with new training parameters"""
        existing_model.dataset_id = int(params['dataset_id'])
        existing_model.epochs = int(params['epochs'])
        existing_model.learn_method = int(params['learn_method'])
        existing_model.patch_size_1 = int(params['m1_patch_size'])
        existing_model.input_size_1 = int(params['m1_input_size'])
        existing_model.weight_path_1 = params['m1_weight_path']
        existing_model.engine_path_1 = params['m1_engine_path']
        existing_model.patch_size_2 = int(
            params['m2_patch_size']) if params['learn_method'] == LearnMethod.PARALLEL else None
        existing_model.input_size_2 = int(
            params['m2_input_size']) if params['learn_method'] == LearnMethod.PARALLEL else None
        existing_model.weight_path_2 = params['m2_weight_path'] if params[
            'learn_method'] == LearnMethod.PARALLEL else None
        existing_model.engine_path_2 = params['m2_engine_path'] if params[
            'learn_method'] == LearnMethod.PARALLEL else None
        existing_model.updated_at = datetime.now().isoformat()

    def _create_new_model(self, params, db):
        """Create new trained model record"""
        trained_model = TrainedModels(
            name=params['model_name'],
            dataset_id=params['dataset_id'],
            epochs=int(params['epochs']),
            learn_method=int(params['learn_method']),
            patch_size_1=int(params['m1_patch_size']),
            input_size_1=int(params['m1_input_size']),
            weight_path_1=params['m1_weight_path'],
            engine_path_1=params['m1_engine_path'],
            patch_size_2=int(
                params['m2_patch_size']) if params['learn_method'] == LearnMethod.PARALLEL else None,
            input_size_2=int(
                params['m2_input_size']) if params['learn_method'] == LearnMethod.PARALLEL else None,
            weight_path_2=params['m2_weight_path'] if params['learn_method'] == LearnMethod.PARALLEL else None,
            engine_path_2=params['m2_engine_path'] if params['learn_method'] == LearnMethod.PARALLEL else None,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        db.add(trained_model)

    def _save_model_to_db(self, params):
        """Save or update model record in database and mark dataset as trained"""
        db_handle = None
        try:
            with get_db() as db:
                db_handle = db
                model_name = params['model_name']
                dataset_id = params['dataset_id']

                # Check for existing active model (matching the unique index criteria)
                existing_model = db.query(TrainedModels) \
                    .filter(func.lower(TrainedModels.name) == model_name.lower()) \
                    .filter(TrainedModels.deleted == 0) \
                    .first()

                if existing_model:
                    Logger.info("Updating existing model: %s", existing_model.name)
                    self._update_existing_model(existing_model, params)
                else:
                    Logger.info("Creating new model: %s", model_name)
                    self._create_new_model(params, db)

                # Mark dataset as trained
                dataset = db.query(Datasets).filter(
                    Datasets.id == dataset_id).first()
                if dataset:
                    dataset.is_trained = True

                db.commit()
                Logger.info("Successfully saved model '%s' to database.", model_name)
                return True
        except Exception:
            if db_handle:
                db_handle.rollback()
            traceback.print_exc()
            return False

    def _invalidate_existing_model(self, model_name):
        """Mark an existing model as deleted in the database if it exists and is active"""
        db_handle = None
        try:
            with get_db() as db:
                db_handle = db
                existing_model = db.query(TrainedModels) \
                    .filter(func.lower(TrainedModels.name) == model_name.lower()) \
                    .filter(TrainedModels.deleted == 0) \
                    .first()
                if existing_model:
                    Logger.info("Invalidating existing model due to training failure: %s", existing_model.name)
                    existing_model.deleted_at = datetime.now().isoformat()
                    existing_model.deleted = 1
                    db.commit()
                    return True
                return False
        except Exception:
            if db_handle:
                db_handle.rollback()
            traceback.print_exc()
            return False

    def _execute_training_command(self, training_params):
        """Execute the actual training command"""
        self.current_epoch = 0
        self.has_completed_epochs = False
        start_time = time.time()

        # Build command
        command = self._build_training_command(training_params)
        print(f"Starting training with command: {' '.join(command)}")

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'

        # Start process
        self._training_process = subprocess.Popen(
            command,
            cwd=BE_FOLDER,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            encoding='utf-8',
            universal_newlines=True,
            env=env
        )

        process = self._training_process

        # Log start message
        if int(training_params['epochs']) >= 1:
            Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                text_key="start_training_log_C2",
                color=COLORS['LIGHT_BLUE'],
                format_args={
                    "dataset_name": training_params['dataset_name'],
                    "epochs": training_params['epochs']
                },
            ))

        # Process output with stop check
        try:
            for line in iter(process.stdout.readline, ''):
                # Check if training was stopped
                if self._training_stopped:
                    break
                line = line.strip()
                if line:
                    self.parse_and_log_line(line)
        except Exception:
            if not self._training_stopped:
                traceback.print_exc()

        process.stdout.close()

        # Only check results if not stopped by user
        if not self._training_stopped:
            return_code = process.wait()
            # Check results and log completion
            self._handle_training_completion(
                return_code, start_time, training_params)
        else:
            # If stopped, ensure process is terminated
            self._terminate_training_process()
            # Invalidate existing model if we were overwriting one
            self._invalidate_existing_model(training_params['model_name'])

    def _build_training_command(self, training_params):
        """Build the training command with all parameters"""
        command = PYTHON_RUNNER.split() + [
            "-u",
            os.path.join(BE_FOLDER, 'flows', 'fastflow', 'train_cli.py'),
            "--data_root", fr'{training_params["data_root"]}',
            "--learn_method", str(training_params['learn_method']),
            "--m1_input_size", training_params['m1_input_size'],
            "--m1_patch_size", training_params['m1_patch_size'],
            "--m1_weight_path", fr'{training_params["m1_weight_path"]}',
            "--backbone", str(FAST_FLOW_BACKBONE),
            "--epochs", str(training_params['epochs']),
            "--batch_size", "10",
        ]

        if str(training_params['learn_method']) == LearnMethod.PARALLEL:
            command += [
                "--m2_input_size", training_params['m2_input_size'],
                "--m2_patch_size", training_params['m2_patch_size'],
                "--m2_weight_path", fr'{training_params["m2_weight_path"]}',
            ]

        return command

    def _handle_training_completion(self, return_code, start_time, training_params):
        """Handle training completion and check results"""
        weight_files_created = False

        # Check if m1 weight file was created
        m1_created = os.path.exists(training_params['m1_weight_path']) and os.path.getmtime(
            training_params['m1_weight_path']) > start_time
        m1_engine_created = os.path.exists(training_params['m1_engine_path']) and os.path.getmtime(
            training_params['m1_engine_path']) > start_time

        # If PARALLEL mode, must check both m1 and m2
        if str(training_params['learn_method']) == LearnMethod.PARALLEL and training_params['m2_weight_path']:
            m2_created = os.path.exists(training_params['m2_weight_path']) and os.path.getmtime(
                training_params['m2_weight_path']) > start_time
            m2_engine_created = os.path.exists(training_params['m2_engine_path']) and os.path.getmtime(
                training_params['m2_engine_path']) > start_time
            weight_files_created = m1_created and m2_created and m1_engine_created and m2_engine_created
        else:
            weight_files_created = m1_created and m1_engine_created

        # Log completion status
        if return_code == 0 and self.has_completed_epochs and weight_files_created:
            # Save to DB only on success
            self._save_model_to_db(training_params)

            Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                text_key='success_training_log_C2',
                color=COLORS['LIGHT_GREEN'],
            ))
        elif not self.has_completed_epochs or not weight_files_created:
            # Invalidate existing model since training failed to replace it
            self._invalidate_existing_model(training_params['model_name'])

            Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                text_key='error_training_log_C2',
                color=COLORS['LIGHT_RED'],
            ))
            print("Could not create weight files.")
        else:
            # Case for return_code != 0
            self._invalidate_existing_model(training_params['model_name'])

            Clock.schedule_once(lambda dt: self.ids.training_log_viewer.add_log_line_key(
                text_key='error_training_log_C2',
                color=COLORS['LIGHT_RED'],
            ))
            print("Could not create weight files")
        self._schedule_result_viewing()

    def _schedule_result_viewing(self):
        """Schedule result viewing with screen presence check"""
        # Cancel any pending result viewing
        if self._pending_result_view:
            Clock.unschedule(self._pending_result_view)

        # Schedule new result viewing check
        self._pending_result_view = Clock.schedule_once(
            self._check_and_mark_result_viewed, 2.0)

    def _check_and_mark_result_viewed(self, dt):
        """Check if user is still on screen before marking result as viewed"""
        self._pending_result_view = None

        # Only mark as viewed if:
        # 1. Training is completed but not viewed yet
        # 2. User is currently on this screen
        if self._is_training_completed_but_not_viewed() and self._screen_active:
            self._mark_result_as_viewed()

    def parse_and_log_line(self, line):
        """Parse log line and format it properly"""

        if not hasattr(self, "_pending_epoch"):
            self._pending_epoch = None

        if not hasattr(self, "_processed_epochs"):
            self._processed_epochs = set()

        if line == "=== Starting Training ===":
            self._pending_epoch = 1  # Start from epoch 1
            self._processed_epochs = set()
            return

        # When encountering Epoch[x]:, confirm epoch is completed
        epoch_complete_match = re.search(r'\[Epoch:(\d+)\]\[Train\]:?\s*', line)
        if epoch_complete_match:
            epoch_num = int(epoch_complete_match.group(1))

            if epoch_num not in self._processed_epochs:
                self.current_epoch = epoch_num
                self.has_completed_epochs = True
                self._processed_epochs.add(epoch_num)

            #     percent_step = max(1, int(self.total_epochs * 0.1))
            #     should_display = (
            #         self.current_epoch == 1 or
            #         self.current_epoch % percent_step == 0 or
            #         self.current_epoch == self.total_epochs
            #     )
            #     if should_display:
            #         formatted_line = f"Epoch {self.current_epoch}/{self.total_epochs}: Processing..."
            #         Clock.schedule_once(lambda dt, l=formatted_line: self.ids.training_log_viewer.add_log_line(
            #             l, [1, 1, 1, 1]
            #         ))
            # return

        # Find "Done" pattern to know completion
        if line == "--- Training complete ---":
            return  # Don't log "Done", will log success message at process.wait()

        # Other lines can be logged for debug (optional)
        # Uncomment line below if you want to see all logs
        Clock.schedule_once(lambda dt, l=line: self.ids.training_log_viewer.add_log_line(
            text=l,
            color=COLORS['LIGHT_GRAY']
        ))

    def scroll_screen_c2_to_default(self):
        """Scroll the screen C2 model training view to its default position (top)."""
        try:
            # Assume ScrollView of screen C2 has id 'scroll_screen_C2_model_training'
            scroll_view = self.ids.get('scroll_screen_C2_model_training', None)
            if not scroll_view:
                print("ScrollView with id 'scroll_screen_C2_model_training' not found")
                return

            def apply_scroll(*args):
                scroll_view.scroll_y = 1.0

            Clock.schedule_once(apply_scroll, 0.1)
        except Exception:
            traceback.print_exc()

    def _save_spinner_selections(self):
        """Save current selections of all FormSpinner"""
        spinner_ids = [
            'c2_dataset_select',
            'patch_size_1_select',
            'input_size_1_select',
            'patch_size_2_select',
            'input_size_2_select'
        ]

        for spinner_id in spinner_ids:
            try:
                if hasattr(self.ids, spinner_id):
                    spinner_widget = getattr(self.ids, spinner_id)

                    spinner = None
                    if hasattr(spinner_widget, 'ids') and hasattr(spinner_widget.ids, 'spinner'):
                        spinner = spinner_widget.ids.spinner
                    elif hasattr(spinner_widget, 'text') and hasattr(spinner_widget, '_dropdown'):
                        # This is already the spinner
                        spinner = spinner_widget

                    if spinner and hasattr(spinner, 'text') and hasattr(spinner, '_dropdown'):
                        if spinner.text and spinner._dropdown: # pylint: disable=protected-access
                            # Find index of selected option
                            children_list = list(
                                reversed(spinner._dropdown.container.children)) # pylint: disable=protected-access
                            for i, child in enumerate(children_list):
                                if getattr(child, 'text', None) == spinner.text:
                                    self._spinner_selections[spinner_id] = {
                                        'text': spinner.text,
                                        'index': i
                                    }
                                    break
            except Exception:
                traceback.print_exc()
                continue

    def _restore_spinner_selections(self):
        """Restore saved selections"""
        def restore_selections(*args):
            for spinner_id, selection in self._spinner_selections.items():
                try:
                    if hasattr(self.ids, spinner_id):
                        spinner_widget = getattr(self.ids, spinner_id)

                        spinner = None
                        if hasattr(spinner_widget, 'ids') and hasattr(spinner_widget.ids, 'spinner'):
                            spinner = spinner_widget.ids.spinner
                        elif hasattr(spinner_widget, 'text') and hasattr(spinner_widget, '_dropdown'):
                            # This is already the spinner
                            spinner = spinner_widget

                        if spinner._dropdown and selection['text'] in spinner.values: # pylint: disable=protected-access
                            # Restore text
                            spinner.text = selection['text']

                            # Highlight option in dropdown
                            children_list = list(
                                reversed(spinner._dropdown.container.children)) # pylint: disable=protected-access
                            if 0 <= selection['index'] < len(children_list):
                                option = children_list[selection['index']]
                                if getattr(option, 'text', None) == selection['text']:
                                    spinner._dropdown.selected_option = option # pylint: disable=protected-access
                except Exception:
                    traceback.print_exc()
                    continue
        Clock.schedule_once(restore_selections, 0.1)

    def on_pre_enter(self, *args):
        self._screen_active = True
        self._display_dataset_images_options()

        if self._should_reset_screen():
            self.scroll_screen_c2_to_default()
            self.clear_errors()
            self.reset_screen_c2()
            self.set_left_mouse_disabled(False)
        else:
            self._save_spinner_selections()
            # If training completed but not viewed, mark as viewed
            if self._is_training_completed_but_not_viewed():
                self._mark_result_as_viewed()
            self._restore_spinner_selections()
        # Always update button state when entering screen
        Clock.schedule_once(
            lambda dt: self._update_training_button_state(), 0.1)

    def on_pre_leave(self, *args):
        """Called before leaving the screen"""
        self._screen_active = False

        # Cancel any pending result viewing since user is leaving
        if self._pending_result_view:
            Clock.unschedule(self._pending_result_view)
            self._pending_result_view = None

    def on_leave(self, *args):
        """Called after the screen is hidden"""
        # Ensure screen is marked as inactive
        self._screen_active = False

    def _display_dataset_images_options(self):
        self.ids.patch_size_1_select.ids.spinner.values = []
        self.ids.input_size_1_select.ids.spinner.values = []
        self.ids.patch_size_2_select.ids.spinner.values = []
        self.ids.input_size_2_select.ids.spinner.values = []
        self.ids.c2_dataset_select.values = []

        try:
            with get_db() as db:
                # Query dataset names
                try:
                    names = db.query(Datasets.name) \
                        .filter(Datasets.deleted_at.is_(None)) \
                        .order_by(Datasets.created_at.desc()) \
                        .all()
                    self.ids.c2_dataset_select.values = [
                        name for (name,) in names]
                except Exception:
                    traceback.print_exc()
                    self.ids.c2_dataset_select.values = []

                # Query PATCH_SIZE_LIST and INPUT_SIZE_LIST directly
                try:
                    configs = db.query(SystemConfig.key, SystemConfig.value)\
                        .filter(SystemConfig.key.in_(["PATCH_SIZE_LIST", "INPUT_SIZE_LIST"]))\
                        .all()
                    config_dict = {key: value for key, value in configs}
                    patch_size_list = list(dict.fromkeys([x.lstrip('0').strip() for x in config_dict.get(
                        "PATCH_SIZE_LIST", "").split(',') if x])) if config_dict.get("PATCH_SIZE_LIST") else []
                    input_size_list = list(dict.fromkeys([x.lstrip('0').strip() for x in config_dict.get(
                        "INPUT_SIZE_LIST", "").split(',') if x])) if config_dict.get("INPUT_SIZE_LIST") else []

                    self.ids.patch_size_1_select.ids.spinner.values = patch_size_list
                    self.ids.patch_size_2_select.ids.spinner.values = patch_size_list
                    self.ids.input_size_1_select.ids.spinner.values = input_size_list
                    self.ids.input_size_2_select.ids.spinner.values = input_size_list
                except Exception:
                    traceback.print_exc()
                    self.ids.patch_size_1_select.ids.spinner.values = []
                    self.ids.patch_size_2_select.ids.spinner.values = []
                    self.ids.input_size_1_select.ids.spinner.values = []
                    self.ids.input_size_2_select.ids.spinner.values = []
        except Exception:
            traceback.print_exc()

    def _wait_for_button_enabled_and_close_loading(self):
        """Check training button status and close loading popup when enabled"""
        def check_button_status(dt):
            try:
                training_button = self.ids.training_button

                # If button is enabled, close loading popup
                if not training_button.disabled:
                    if hasattr(self, 'loading_popup') and self.loading_popup:
                        self.loading_popup.opacity = 0
                        self.loading_popup.dismiss()
                        self.loading_popup = None

                        self.ids.training_log_viewer.add_log_line_key(
                            text_key='stop_training_log_C2',
                            color=COLORS['LIGHT_RED'],
                        )
                    return False  # Stop scheduling
                else:
                    # If button is still disabled, continue checking after 0.1s
                    return True  # Continue scheduling

            except Exception:
                # If error occurs, close loading popup to avoid hanging
                if hasattr(self, 'loading_popup') and self.loading_popup:
                    self.loading_popup.opacity = 0
                    self.loading_popup.dismiss()
                    self.loading_popup = None
                traceback.print_exc()
                return False  # Stop scheduling

        # Check every 0.1s
        Clock.schedule_interval(check_button_status, 0.1)

    def _restore_ui_state(self):
        """Centralized UI state restoration method"""
        self.set_left_mouse_disabled(False)
        Clock.schedule_once(
            lambda dt: self._update_training_button_state(), 0)

    def _check_existing_weights(self, model_name, training_mode):
        """Check if training weights already exist for the model"""
        try:
            with get_db() as db:
                trained_model = db.query(TrainedModels) \
                    .filter(TrainedModels.name == model_name) \
                    .filter(TrainedModels.deleted_at.is_(None)) \
                    .first()

                if not trained_model:
                    return False

                weight_path_1 = trained_model.weight_path_1
                weight_path_2 = trained_model.weight_path_2

                # Check based on training mode
                if training_mode == self.app.lang.get('learn_method_1'):
                    return weight_path_1 and os.path.isfile(weight_path_1)
                else:
                    return (weight_path_1 and os.path.isfile(weight_path_1) and
                           weight_path_2 and os.path.isfile(weight_path_2))

        except Exception:
            traceback.print_exc()
            return False

    def _terminate_training_process(self):
        """Terminate the training subprocess and all its children forcefully"""
        if not (hasattr(self, '_training_process') and self._training_process):
            return

        try:
            pid = self._training_process.pid
            Logger.info("Forcefully terminating training process %s and its children...", pid)
            
            parent = psutil.Process(pid)
            # Kill children first recursively
            for child in parent.children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            
            # Kill the parent process
            parent.kill()
            # Wait for it to exit
            parent.wait(timeout=5)
            Logger.info("Process %s and all decoration child processes have been terminated.", pid)
            
        except psutil.NoSuchProcess:
            Logger.info("Process already terminated.")
        except Exception:
            # Fallback to standard termination if psutil fails
            try:
                if self._training_process:
                    self._training_process.kill()
                    self._training_process.wait(timeout=2)
            except Exception:
                pass
            traceback.print_exc()

    def _handle_stop_confirmation(self):
        """Handle the stop training confirmation logic"""
        try:
            # Check if training is actually running
            if not self._is_training_running():
                return True

            model_name = self.ids.c2_model_name_input.text
            training_mode = self.ids.c2_training_method_select.text

            # Mark training as stopped
            self._training_stopped = True
            
            # Formally terminate the process tree
            self._terminate_training_process()

            # Show loading popup and wait for UI to reflect stopped state
            self.loading_popup = self.popup.create_loading_popup(
                title='loading_popup')
            self.loading_popup.open()
            self._wait_for_button_enabled_and_close_loading()

            return True

        except Exception:
            traceback.print_exc()
            self._restore_ui_state()
            return False

    def stop_training(self):
        """Stop the currently running training process immediately"""
        try:
            # Only allow stopping if training is actually running
            if not self._is_training_running():
                return

            confirm_popup = self.popup.create_confirmation_popup(
                title='confirm_popup',
                message='stop_training_confirm_C2',
                on_confirm=self._handle_stop_confirmation,
            )
            confirm_popup.open()

        except Exception:
            traceback.print_exc()
            self._restore_ui_state()

    @contextmanager
    def training_session(self):
        """Context manager to manage training session"""
        try:
            # Setup phase
            self.set_left_mouse_disabled(True)

            # Only allow training if not currently running
            if self._is_training_running():
                yield False
                return

            self.ids.training_log_viewer.clear_logs_key()

            # Reset flags when starting new training
            self._training_completed = False
            self._result_viewed = False

            yield True

        except Exception:
            traceback.print_exc()
            yield False
        finally:
            # Cleanup phase - always executed
            self.set_left_mouse_disabled(False)
            Clock.schedule_once(
                lambda dt: self._update_training_button_state(), 0.1)

    def start_training(self):
        """Start training with context manager"""
        with self.training_session() as can_proceed:
            if not can_proceed:
                return

            # Validate inputs before starting training thread
            validation_result = self._validate_training_inputs()
            if not validation_result or not validation_result['is_valid']:
                self._handle_validation_errors(
                    validation_result['errors'] if validation_result else [],
                    validation_result['show_log'] if validation_result else None,
                    validation_result['training_status_placeholder'] if validation_result else False
                )
                return

            # Start logging thread with validation result
            self.start_log_thread(validation_result)

    def clear_training_logs(self):
        """Clear all training logs from the log viewer"""
        try:
            self.ids.training_log_viewer.clear_logs_key(default_key="training_status_placeholder_C2")
        except (AttributeError, ReferenceError):
            traceback.print_exc()

    def clear_errors(self):
        """Clear all error messages from input fields"""
        self.ids.c2_model_name_input.error_message = ''
        self.ids.c2_dataset_select.error_message = ''
        self.ids.c2_epoch_input.error_message = ''

    def reset_screen_c2(self):
        """Reset entire C2 screen to default state"""
        self.clear_training_logs()
        self.ids.training_log_viewer.reset_scroll_to_top()

        self.ids.c2_model_name_input.text = ''

        self.ids.c2_dataset_select.text = ''

        self.ids.c2_training_method_select.text = self.ids.c2_training_method_select.label[0]

        spinner_ids = [
            'patch_size_1_select',
            'input_size_1_select',
            'patch_size_2_select',
            'input_size_2_select'
        ]

        for spinner_id in spinner_ids:
            spinner = getattr(self.ids, spinner_id).ids.spinner
            spinner.text = spinner.values[0] if spinner.values else ''

        self.ids.c2_epoch_input.text = '10'

        # Reset epoch tracking
        self.current_epoch = 0
        self.total_epochs = 0
