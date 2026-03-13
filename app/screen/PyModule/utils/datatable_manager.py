"""
This module manages data table display within a Kivy application.
It provides tools for loading data from a database, rendering it in a table with pagination,
and showing placeholders when no data is available.

Main features:
- Load data from SQLAlchemy models
- Display and paginate results in a Kivy DataTable
- Dynamically build pagination controls
- Support multiple cell types (text, image, button, copy button, etc.)
"""

import math
import traceback

from kivy.app import App
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout
from sqlalchemy import desc

from app.libs.constants.colors import COLORS
from app.libs.constants.default_values import DefaultValuesTable
from app.libs.widgets.components import KeyLabel
from db.session import get_db


class EmptyTableLabel(FloatLayout):
    """
    A widget that displays a "No data" placeholder when the table is empty.

    Attributes:
        table (Widget): The target data table this label belongs to.
        label (KeyLabel): The text label that displays the placeholder message.
    """

    def __init__(self, table, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.table = table
        self.label = None
        self.bind(size=self._update_label, pos=self._update_label)
        self.table.bind(size=self._update_label, pos=self._update_label)
        self.size_hint_x = None
        self.pos_hint = {'x': 0, 'y': 0}

    def _update_label(self, *args):
        if not self.label:
            self.label = KeyLabel(
                text_key='no_data_placeholder',
                font_size=dp(20),
                color=[0.6, 0.6, 0.6, 1],
                size_hint=(None, None),
                halign='center',
                valign='middle',
                padding=[0, dp(40), 0, 0],
            )
            self.add_widget(self.label)

        # Update label position and size
        self.label.text_size = (self.table.width, None)
        self.label.size = self.label.texture_size
        self.label.pos = (
            self.table.x + (self.table.width - self.label.width) / 2,
            self.table.y + (self.table.height - self.label.height) / 2
        )


class DataTableManager:
    """Access and manage a defined DataTable in kivy"""

    DEFAULT_TEXT_COLOR = COLORS['MEDIUM_BLACK']
    VALID_TYPES = ['str', 'int', 'float', 'image', 'button', 'button_backup', 'button_copy']

    def __init__(
        self,
        screen,
        table_id,
        pagination_box_id,
        headers,
        types,
        settings_file=None,
        db_model=None,
        db_headers=None,
        config_fields=None,
        custom_message=False,
        markup_columns=None,
        translation_columns=None
        ):
        self.screen = screen  # Reference to the screen containing the table
        self.table_id = table_id
        self.pagination_box_id = pagination_box_id
        self.headers = headers
        self.types = types
        self.settings_file = settings_file
        self._default_color = self.DEFAULT_TEXT_COLOR
        self.__validate_types()
        # Variable to store state
        self.all_rows = []
        self.current_page = 1
        self.rows_per_page = 5
        self.db_model = db_model
        self.db_headers = db_headers
        self.config_fields = config_fields
        self.custom_message = custom_message
        self.markup_columns = markup_columns or []
        self.translation_columns = translation_columns or []
        self.app = App.get_running_app()

    def __validate_types(self):
        for type_name in self.types:
            if type_name not in self.VALID_TYPES:
                raise ValueError(f"Unknown type: {type_name}. Allowed types are {self.VALID_TYPES}")

    def load_settings_from_db(self, keep_current_page=True, target_page=1):
        """
        Dynamic: Get data from DB, build self.all_rows similar to JSON, use db_headers to get data.
        db_headers: list of DB/model field names (e.g.: ["name", "updated_at", ...])
        config_fields: list of DB/model field names for 'config' dict
        """
        if self.config_fields is None:
            self.config_fields = []

        all_rows = []
        with get_db() as db:
            records = (
                db.query(self.db_model)
                .filter(self.db_model.deleted_at.is_(None))
                .order_by(desc(self.db_model.id))
                .all()
            )
            for record in records:
                item = {}
                for db_h in self.db_headers:
                    value = getattr(record, db_h, "")
                    # Format date for updated_at/created_at if needed
                    if db_h in ["updated_at", "created_at"] and value:
                        value = value[:10].replace("-", "/")
                    item[db_h] = value
                # Build config dict if available
                config = {}
                for field in self.config_fields:
                    config[field] = getattr(record, field, "")
                if self.config_fields:
                    item["config"] = config
                # Add button field if needed
                if "button" in self.db_headers:
                    item["button"] = "placeholder"
                all_rows.append(item)

        self.all_rows = all_rows
        if not keep_current_page:
            self.current_page = target_page
        self.display_current_page()
        self.create_pagination_controls()

    def display_current_page(self):
        """Display data of the current page"""
        table = self.screen.ids[self.table_id]
        table.clear_widgets()

        # Headers
        for index, header in enumerate(self.headers):
            if table.cols_width and table.cols_width[index] != -1:
                table.add_widget(Factory.TableHeaderCell(text=header, size_hint_x=None, width=table.cols_width[index]))
            else:
                table.add_widget(Factory.TableHeaderCell(text=header))

        if not self.all_rows:
            self._display_empty_table(table)
            return

        # Has data
        self._display_data_table(table)

    def get_all_rows(self):
        """
        Return current all_rows without reloading from DB
        Returns:
            list: List of all rows
        """
        return self.all_rows

    def find_page_for_record(self, record_name, name_field='name'):
        """
        Find the page containing a record with the given name
        Args:
            record_name: Name of the record to find
            name_field: Field name containing the record name (default 'name')
        Returns:
            int: Page number containing the record, or 1 if not found
        """
        if not self.all_rows:
            return 1

        try:
            names = [row.get(name_field) for row in self.all_rows]
            record_index = names.index(record_name)
            return math.ceil((record_index + 1) / self.rows_per_page)
        except ValueError:
            return 1

    def _display_empty_table(self, table):
        """Display table when there is no data"""
        table.has_data = False

        # Create empty cells
        for _ in range(self.rows_per_page):
            for _ in range(len(self.headers)):
                label = Factory.TableCell(text="", row_index=-1)
                table.add_widget(label)

        # Add "NO DATA" label to table
        empty_label = EmptyTableLabel(table)
        table.add_widget(empty_label)

    def _display_data_table(self, table):
        table.has_data = True
        pagination_box = self.screen.ids[self.pagination_box_id]
        pagination_box.opacity = 1
        pagination_box.disabled = False

        start = (self.current_page - 1) * self.rows_per_page
        end = start + self.rows_per_page
        rows_to_display = self.all_rows[start:end]

        for idx, item in enumerate(rows_to_display):
            values = [value for key, value in item.items() if key != 'config']

            actual_row_index = start + idx
            # Display data based on defined types
            self.add_row_to_table(table, values, idx, actual_row_index, row_data=item)

        # Fill empty rows
        empty_rows = self.rows_per_page - len(rows_to_display)
        last_idx = len(rows_to_display)

        if empty_rows > 0:
            empty_row = [''] * len(self.types)
            for i in range(empty_rows):
                actual_row_index = start + last_idx + i
                self.add_row_to_table(table, empty_row, last_idx+i, actual_row_index)

    def add_row_to_table(self, table, datas, index, actual_row_index, row_data=None):
        """Add row to table with cell factory based on types"""
        # datas is a list of values for each row
        for i, data in enumerate(datas):
            enable_markup = i in self.markup_columns
            enable_translation = i in self.translation_columns

            if data == '': # empty case
                if table.cols_width and table.cols_width[i] != -1:
                    cell_data = Factory.TableCell(
                        text=str(''),
                        row_index=index,
                        size_hint_x=None,
                        width=table.cols_width[i],
                        enable_markup=enable_markup
                        )
                else:
                    cell_data = Factory.TableCell(
                        text=str(''),
                        row_index=index,
                        enable_markup=enable_markup
                        )
                table.add_widget(cell_data)
            elif self.types[i] == 'button':
                if data == 'disable': # not display
                    if table.cols_width and table.cols_width[i] != -1:
                        cell_data = Factory.TableCell(
                            text=str(''),
                            row_index=index,
                            size_hint_x=None,
                            width=table.cols_width[i],
                            enable_markup=enable_markup
                            )
                    else:
                        cell_data = Factory.TableCell(
                            text=str(''),
                            row_index=index,
                            enable_markup=enable_markup
                            )
                    table.add_widget(cell_data)
                else:
                    # Create button
                    if table.cols_width and table.cols_width[i] != -1:
                        cell_button = Factory.TableButtonCell(
                            row_index=index,
                            table_manager=self,
                            size_hint_x=None, width=table.cols_width[i]/2,
                            custom_message=self.custom_message
                        )
                    else:
                        cell_button = Factory.TableButtonCell(
                            row_index=index,
                            table_manager=self,
                            custom_message=self.custom_message
                        )
                    table.add_widget(cell_button)
            elif self.types[i] == 'button_backup':
                if data == 'disable': # not display
                    if table.cols_width and table.cols_width[i] != -1:
                        cell_data = Factory.TableCell(
                            text=str(''),
                            row_index=index,
                            size_hint_x=None,
                            width=table.cols_width[i],
                            enable_markup=enable_markup
                            )
                    else:
                        cell_data = Factory.TableCell(
                            text=str(''),
                            row_index=index,
                            enable_markup=enable_markup
                            )
                    table.add_widget(cell_data)
                else:
                    cell_button = Factory.TableBackupButtonCell(
                        row_index=index,
                        table_manager=self,
                        custom_message=self.custom_message
                    )
                    table.add_widget(cell_button)
            elif self.types[i] == 'image':
                # Create image cell
                if table.cols_width and table.cols_width[i] != -1:
                    cell_image = Factory.TableImageCell(
                        row_index=index,
                        image_source=data,
                        size_hint_x=None, width=table.cols_width[i]
                    )
                else:
                    cell_image = Factory.TableImageCell(
                        row_index=index,
                        image_source=data
                    )
                table.add_widget(cell_image)
            elif self.types[i] == 'button_copy':
                if data == 'disable': # not display
                    if table.cols_width and table.cols_width[i] != -1:
                        cell_data = Factory.TableCell(
                            text=str(''),
                            row_index=index,
                            size_hint_x=None,
                            width=table.cols_width[i],
                            enable_markup=enable_markup
                            )
                    else:
                        cell_data = Factory.TableCell(
                            text=str(''),
                            row_index=index,
                            enable_markup=enable_markup
                            )
                    table.add_widget(cell_data)
                else:
                    # Check if we should disable edit button (for trained datasets)
                    disable_edit = False
                    if row_data and 'is_trained' in row_data:
                        is_trained_value = row_data['is_trained']
                        # Check if is_trained is the 'done' status
                        if is_trained_value == 'trained_status_done_C1':
                            disable_edit = True

                    cell_button = Factory.TableCopyButtonCell(
                        row_index=index,
                        table_manager=self,
                        custom_message=self.custom_message,
                        disable_edit_button=disable_edit
                    )
                    table.add_widget(cell_button)
            else:
                # Apply cols_width to regular text cells
                if enable_translation:
                    # Handle translation with potential format args
                    if isinstance(data, dict) and 'text_key' in data:
                        text_key = data['text_key']
                        format_args = data.get('format_args', None)
                    else:
                        text_key = str(data)
                        format_args = None

                    if table.cols_width and table.cols_width[i] != -1:
                        cell_data = Factory.TableCell(
                            text="",
                            text_key=text_key,
                            format_args=format_args,
                            row_index=index,
                            size_hint_x=None,
                            width=table.cols_width[i],
                            enable_markup=enable_markup
                        )
                    else:
                        cell_data = Factory.TableCell(
                            text="",
                            text_key=text_key,
                            format_args=format_args,
                            row_index=index,
                            enable_markup=enable_markup
                        )
                else:
                    # Regular text cell
                    if table.cols_width and table.cols_width[i] != -1:
                        cell_data = Factory.TableCell(
                            text=str(data),
                            row_index=index,
                            size_hint_x=None,
                            width=table.cols_width[i],
                            enable_markup=enable_markup
                        )
                    else:
                        cell_data = Factory.TableCell(
                            text=str(data),
                            row_index=index,
                            enable_markup=enable_markup
                        )
                table.add_widget(cell_data)

    def go_to_page(self, page_number):
        """Go to the specified page"""
        total_pages = math.ceil(len(self.all_rows) / self.rows_per_page)
        if 1 <= page_number <= total_pages:
            self.current_page = page_number
            self.display_current_page()
            self.create_pagination_controls()

    def get_pagination(self, current_page, total_pages):
        """
        Calculate page numbers to display with ellipsis mechanism.

        Args:
            current_page (int): Current active page number
            total_pages (int): Total number of pages available

        Returns:
            list: List of page numbers and '...' ellipsis to display

        Examples:
            - Total 5 pages: [1, 2, 3, 4, 5]
            - Page 1/100: [1, 2, 3, 4, 5, 6, 7, '...', 100]
            - Page 50/100: [1, '...', 48, 49, 50, 51, 52, '...', 100]
            - Page 98/100: [1, '...', 94, 95, 96, 97, 98, 99, 100]
        """
        max_visible_pages = DefaultValuesTable.MAX_VISIBLE_PAGES
        edge_pages = DefaultValuesTable.EDGE_PAGES
        surrounding_pages = DefaultValuesTable.SURROUNDING_PAGES
        ellipsis = DefaultValuesTable.ELLIPSIS

        # Simple case: display all pages when total is small
        if total_pages <= max_visible_pages:
            return list(range(1, total_pages + 1))

        # Current page is near the beginning
        if current_page <= max_visible_pages:
            return list(range(1, max_visible_pages + 1)) + [ellipsis, total_pages]

        # Current page is near the end
        if current_page >= total_pages - max_visible_pages + 1:
            start_page = total_pages - max_visible_pages + 1
            return [edge_pages, ellipsis] + list(range(start_page, total_pages + 1))

        # Current page is in the middle
        return [
            edge_pages,
            ellipsis,
            *range(current_page - surrounding_pages, current_page + surrounding_pages + 1),
            ellipsis,
            total_pages
        ]

    def create_pagination_controls(self):
        """Create pagination buttons"""
        try:
            def make_button(text, callback, enabled=True, active=False):
                btn = Factory.PaginationButton(text=str(text))
                btn.disabled = not enabled
                btn.active = active

                if enabled:
                    btn.bind(on_release=callback)
                return btn

            pagination_box = self.screen.ids[self.pagination_box_id]
            pagination_box.clear_widgets()

            if self.all_rows:
                pagination_box.opacity = 1
                pagination_box.disabled = False
            else: #No data
                pagination_box.opacity = 0
                pagination_box.disabled = True
                return

            total_pages = math.ceil(len(self.all_rows) / self.rows_per_page)
            current = self.current_page

            # Page numbers
            if total_pages > 1:
                prev_btn = make_button('<', lambda x: self.go_to_page(current - 1), current > 1)
                pagination_box.add_widget(prev_btn)

                page_items = self.get_pagination(current, total_pages)
                for item in page_items:
                    if item == '...':
                        btn = Factory.PaginationButton(text=str(item))
                        btn.disabled = True
                        btn.canvas.before.clear()
                        pagination_box.add_widget(btn)
                    else:
                        btn = make_button(
                            text=str(item),
                            callback=lambda btn, page=item: self.go_to_page(page),
                            enabled=True,
                            active=(item == current)
                        )
                        pagination_box.add_widget(btn)

                next_btn = make_button('>', lambda x: self.go_to_page(current + 1), current < total_pages)
                pagination_box.add_widget(next_btn)

            # Spacer
            spacer = Factory.Widget()
            spacer.size_hint_x = 1.0
            pagination_box.add_widget(spacer)

            # Info
            start_record = (current - 1) * self.rows_per_page + 1
            end_record = min(current * self.rows_per_page, len(self.all_rows))
            total_records = len(self.all_rows)
            info_label = Factory.PaginationInfo(start_record, end_record, total_records)
            pagination_box.add_widget(info_label)

        except Exception:
            traceback.print_exc()
