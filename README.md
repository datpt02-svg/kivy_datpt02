# EVS UI

[![Build Status][build-badge]][build-link]
[![License][license-badge]][license-link]

> Ứng dụng desktop xử lý và trực quan hóa dữ liệu 3D hiệu suất cao.

## Giới thiệu

Dự án này là một ứng dụng desktop được xây dựng bằng Python, cung cấp các công cụ để phân tích, xử lý và hiển thị các tập dữ liệu 3D. Giao diện người dùng được phát triển bằng framework **Kivy**, và các tác vụ tính toán nặng được tăng tốc bởi **CuPy** trên các GPU NVIDIA.

Dự án này tuân theo các nguyên tắc về mã nguồn mở và được thiết kế để dễ dàng cài đặt và sử dụng.

## Yêu cầu

Trước khi bắt đầu, hãy đảm bảo hệ thống của bạn đáp ứng các yêu cầu sau:

* **Hệ điều hành**: Windows, macOS, hoặc Linux.
* **Phần cứng**:
    * **Card đồ họa NVIDIA**: Bắt buộc để sử dụng thư viện `cupy-cuda12x`.
    * **CUDA Toolkit**: Đã cài đặt phiên bản tương thích (ví dụ: CUDA 12.x).
* **Phần mềm**:
    * **Python 3.9**.
    * **uv**: Một trình quản lý gói và môi trường ảo Python cực nhanh. Script cài đặt sẽ tự động cài `uv` nếu cần.

## Cài đặt

Dưới đây là hướng dẫn để thiết lập dự án trên máy của bạn.

### 1. Tải mã nguồn

Clone repository này về máy của bạn:

```bash
git clone [URL_CUA_REPOSITORY]
cd [TEN_THU_MUC_DU_AN]
```

### 2. Cấu hình Biến Môi trường

Dự án này sử dụng tệp `.env` để quản lý các cấu hình riêng tư hoặc nhạy cảm.

1.  Tạo một bản sao của tệp `.env.example` (nếu có) và đổi tên thành `.env`:
    ```bash
    # Windows (Command Prompt)
    copy .env.example .env

    # macOS / Linux
    cp .env.example .env
    ```
2.  Mở tệp `.env` và điền các giá trị cần thiết. Xem phần [Cấu hình Biến Môi trường](#cấu-hình-biến-môi-trường-environment-variables) để biết chi tiết về các biến.

### 3. Thiết lập môi trường

Chúng tôi cung cấp hai cách để cài đặt môi trường và các gói phụ thuộc.

#### Tùy chọn A: Cài đặt tự động (Chỉ dành cho Windows)

Nếu bạn đang sử dụng Windows, hãy chạy tập lệnh `setup.bat`. Nó sẽ tự động hóa toàn bộ quá trình:

```bash
setup.bat
```
Tập lệnh này sẽ:
1.  Cài đặt `uv` nếu nó chưa tồn tại.
2.  Sử dụng `uv` để cài đặt Python 3.9.
3.  Cài đặt tất cả các gói phụ thuộc được định nghĩa trong `uv.lock`.

#### Tùy chọn B: Cài đặt thủ công (Windows, macOS, Linux)

Nếu bạn không dùng Windows hoặc muốn kiểm soát quá trình cài đặt:

1.  **Cài đặt `uv`**:
    Thực thi lệnh sau trong terminal của bạn:
    ```bash
    # macOS / Linux
    curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

    # Windows (PowerShell)
    powershell -c "irm [https://astral.sh/uv/install.ps1](https://astral.sh/uv/install.ps1) | iex"
    ```

2.  **Cài đặt các gói phụ thuộc**:
    Sử dụng `uv sync` để tạo môi trường ảo (`.venv`) và cài đặt tất cả các gói từ tệp `uv.lock`.
    ```bash
    uv sync
    ```

## Bắt đầu nhanh (Quick Start)

Sau khi cài đặt thành công, bạn có thể khởi chạy ứng dụng bằng lệnh sau:

```bash
uv run python main.py
```

Lệnh này sẽ thực hiện hai việc:
1.  Tự động cập nhật cơ sở dữ liệu lên phiên bản mới nhất bằng `alembic`.
2.  Khởi chạy giao diện chính của ứng dụng.

## Cấu hình Biến Môi trường (Environment Variables)

Các biến sau có thể được cấu hình trong tệp `.env` để thay đổi hành vi của ứng dụng.

| Biến (Variable)                | Giá trị Mặc định (Default) | Mô tả                                                               |
| ------------------------------ | -------------------------- | ------------------------------------------------------------------- |
| `BE_FOLDER`                    | `../../logic/2.source`     | Đường dẫn đến thư mục backend (logic) của dự án.                    |
| `DATA_FOLDER`                  | `[FE_FOLDER]`              | Thư mục gốc để lưu trữ dữ liệu người dùng. Mặc định là thư mục frontend. |
| `RAW_PATH`                     | `''`                       | Đường dẫn đến dữ liệu thô (raw data).                               |
| `DEBUG`                        | `0`                        | Bật/tắt chế độ gỡ lỗi (1 để bật, 0 để tắt).                          |
| `DOT_POINT`                    | `0.95`                     | Ngưỡng giá trị cho việc phát hiện điểm (dot point).                  |
| `DETECT_AREA_SPLIT`            | `Không có`                 | Cấu hình phân chia khu vực phát hiện.                               |
| `SHOW_IMAGE_WINDOW_WIDTH`      | `1280`                     | Chiều rộng mặc định của cửa sổ hiển thị hình ảnh.                   |
| `SHOW_IMAGE_WINDOW_HEIGHT`     | `960`                      | Chiều cao mặc định của cửa sổ hiển thị hình ảnh.                    |
| `SHOW_HIS_IMAGE_WINDOW_WIDTH`  | `900`                      | Chiều rộng của cửa sổ hiển thị biểu đồ histogram.                   |
| `SHOW_HIS_IMAGE_WINDOW_HEIGHT` | `600`                      | Chiều cao của cửa sổ hiển thị biểu đồ histogram.                    |
| `PATCH_SIZE_LIST`              | `448,896,1792`             | Danh sách kích thước các patch, phân tách bằng dấu phẩy.             |
| `INPUT_SIZE_LIST`              | `224,448,672`              | Danh sách kích thước đầu vào, phân tách bằng dấu phẩy.              |
| `USE_SENSOR`                   | `1`                        | Bật/tắt việc sử dụng cảm biến (1 để bật, 0 để tắt).                  |
| `ADD_QUEUE_FLAG`               | `0`                        | Cờ để bật/tắt việc thêm vào hàng đợi (queue).                       |
| `FAST_FLOW_BACKBONE`           | `wide_resnet50_2`          | Tên của mô hình backbone cho FastFlow.                              |


## Phát triển (Development)

Phần này dành cho các nhà phát triển muốn tùy chỉnh dự án.

### Thiết lập Môi trường Phát triển

Thực hiện theo các bước trong [Cài đặt thủ công](#tùy-chọn-b-cài-đặt-thủ-công-windows-macos-linux) để tạo một môi trường phát triển cô lập.

### Chạy Kiểm thử (Running Tests)

> **Lưu ý**: Cung cấp hướng dẫn chạy bộ kiểm thử của bạn ở đây.

Ví dụ, nếu dự án của bạn sử dụng `pytest`:
```bash
# Cài đặt pytest nếu chưa có
uv pip install pytest

# Chạy tất cả các bài kiểm thử
uv run pytest
```

### Định dạng Mã nguồn (Code Style)

> **Lưu ý**: Nêu rõ các công cụ định dạng và kiểm tra mã nguồn bạn sử dụng.

Ví dụ, nếu dự án của bạn sử dụng `ruff`:
```bash
# Kiểm tra lỗi mã nguồn
uv run ruff check .

# Tự động sửa lỗi và định dạng mã
uv run ruff format .
```



<!-- Biến Markdown cho các liên kết và huy hiệu -->
[build-badge]: https://img.shields.io/badge/build-passing-brightgreen
[build-link]: #
[license-badge]: https://img.shields.io/badge/license-Apache%202.0-blue
[license-link]: LICENSE


### Build EXE
1. Chạy lệnh build:
   * Build bản có console:
   ```bash
   build.bat --console
   ```
   * Build bản không có console:
   ```bash
   build.bat
   ``` hoặc click đúp vào file build.bat

   Sau khi thành công, file thực thi sẽ nằm tại `dist/evs-ui/evs-ui.exe`.

2. Tham khao example.env để tạo tệp `.env` trong cùng thư mục với file `evs-ui.exe` (tức `dist/evs-ui/.env`).
   - **BE_FOLDER**: trỏ đến thư mục chứa code logic của Event Visual (ví dụ: `../../logic/2.source` hoặc một đường dẫn tuyệt đối như `D:/project/logic/2.source`).
   - **DATA_FOLDER**: đường dẫn nơi lưu dữ liệu được sinh ra khi chạy ứng dụng (ví dụ: `D:/evs-data` hoặc `./data`).
   - Các tham số còn lại giữ nguyên như mặc định.

   Ví dụ nội dung `.env` (chỉ cần chỉnh `BE_FOLDER` và `DATA_FOLDER` theo máy của bạn, các dòng khác giữ nguyên):
   ```env
   ## PATHS
   BE_FOLDER=../../logic/2.source
   DATA_FOLDER=./
   RAW_PATH=./data/data_raw/dot/test-raw-dot.raw
   PIPE_TO_UI_NAME = \\.\pipe\mypipe_to_ui
   PYTHON_RUNNER=.\_internal\.venv\Scripts\pythonw.exe
   ## SETTINGS
   USE_SENSOR=0
   ADD_QUEUE_FLAG=0
   FAST_FLOW_BACKBONE=wide_resnet50_2
   ```

   Gợi ý:
   - Có thể dùng đường dẫn tuyệt đối cho `BE_FOLDER` và `DATA_FOLDER` để tránh sai lệch tương đối khi di chuyển thư mục.
   - Nếu `DATA_FOLDER` là đường dẫn tương đối (ví dụ `./data`), dữ liệu sẽ được lưu tương đối với thư mục chứa `evs-ui.exe`.

   Lưu ý:
   - **Nếu chạy local thì cần xóa PYTHON_RUNNER ở trong .env hoặc thay PYTHON_RUNNER=uv run**
   - **Tắt app trước khi thực hiện build**