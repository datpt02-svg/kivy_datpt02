"""
Dataset Spinner Utility
=======================

This module defines the `DatasetSpinner` class — a helper for dynamically
loading and displaying dataset file names (e.g., `.json` files) into a Kivy
Spinner widget.

It supports two loading modes:
1. From a configuration file (`config/c1_data_selection.json`)
2. From a target folder containing dataset files.

Usage example:
--------------
    spinner_helper = DatasetSpinner(screen=self, spinner_id="dataset_spinner", folder_path="data/")
    spinner_helper.load_spinner_from_folder(include_no_option=True)
"""

import json
import os
import traceback


class DatasetSpinner:
    """
    A helper class for managing dataset name lists and binding them to
    a Kivy Spinner widget.

    Attributes:
        screen (object): The parent Kivy screen containing the Spinner.
        spinner_id (str): The widget ID of the Spinner to update.
        folder_path (str): Path to the folder containing dataset files.
        extension (str): File extension to filter by (default `.json`).
        dataset_names (list[str]): List of dataset names or file names.
    """

    def __init__(self, screen, spinner_id, folder_path=None, extension='.json'):
        self.screen = screen
        self.spinner_id = spinner_id
        self.dataset_names = []
        self.folder_path = folder_path
        self.extension = extension

    def load_dataset_names(self, dt=None):
        """Load danh sách tên các bộ dữ liệu từ settings file"""
        try:
            settings_file = "config/c1_data_selection.json"
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.dataset_names = [
                        row["name"] for row in data.get("rows", [])
                    ]
                    spinner = self.screen.ids[self.spinner_id]
                    if self.dataset_names:
                        spinner.values = self.dataset_names
                    else:
                        spinner.values = []
                        spinner.hint_text = 'Chưa có bộ dữ liệu nào'
        except Exception as e:
            print(f"Lỗi khi load danh sách bộ dữ liệu: {str(e)}")
            traceback.print_exc()


    def load_spinner_from_folder(
        self,
        dt=None,
        include_no_option=False,
        no_option_text='Không có Bias',
        keep_selected_text=False
        ):
        """Load danh sách tên các file .json trong folder và cập nhật vào Spinner (giữ nguyên đuôi theo self.extension)"""
        try:
            if not os.path.exists(self.folder_path):
                print(f"Thư mục không tồn tại: {self.folder_path}")
                return

            files_with_time = [
                (f, os.path.getmtime(os.path.join(self.folder_path, f)))
                for f in os.listdir(self.folder_path)
                if f.endswith(self.extension) and os.path.isfile(os.path.join(self.folder_path, f))
            ]
            files_with_time.sort(key=lambda x: x[1], reverse=True)
            self.dataset_names = [f for f, _ in files_with_time]

            spinner = self.screen.ids[self.spinner_id]
            current_text = spinner.text

            if not self.dataset_names:
                # When no data is found, use a special item
                spinner.values = []
                spinner.text = ""  # Reset text to show hint
                return

            if include_no_option:
                self.dataset_names.insert(0, no_option_text)

            spinner.values = self.dataset_names
            if keep_selected_text and current_text in self.dataset_names:
                spinner.text = current_text
            else:
                spinner.text = ""

        except Exception as e:
            print(f"Lỗi khi load danh sách file từ thư mục: {str(e)}")
            traceback.print_exc()
