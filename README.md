# Phiên dịch Anh – Việt thời gian thực (Python / Kivy / Android)

Ứng dụng Android viết bằng Python: nói tiếng Anh hoặc tiếng Việt, app hiện chữ và **dịch ngay trong lúc bạn đang nói**, hết câu thì dịch chính xác, lưu lịch sử và **đọc to bản dịch**. Dùng như một phiên dịch viên cho cuộc hội thoại hai chiều.

## Tính năng

- **Hai nút lớn:** *English* (người nói tiếng Anh) và *Tiếng Việt*. Nhấn để nghe, nhấn lại (DỪNG) để tắt.
- **Dịch realtime:** kết quả nhận dạng tạm được dịch liên tục (khoảng 0,45 giây một lần), nên bản dịch hiện ra khi người nói chưa dứt câu.
- **Nghe liên tục:** sau mỗi câu app đọc bản dịch rồi tự nghe tiếp. Trong lúc đọc, mic tạm dừng để app không tự thu lại tiếng loa.
- **Đọc bản dịch** bằng giọng Android (Text-to-Speech). Chạm vào một dòng trong lịch sử để nghe lại.
- **Ô gõ chữ:** dịch ngay khi gõ, nút `EN > VI` / `VI > EN` để đổi chiều.
- **Google Translate:** không có API key thì dùng endpoint miễn phí; nhập **Google Cloud Translation API key** trong *Cài đặt* thì dùng API chính thức, ổn định hơn.

## Cấu trúc

| File | Vai trò |
|---|---|
| `main.py` | Giao diện Kivy và luồng xử lý nghe → dịch → đọc |
| `android_speech.py` | Gọi `SpeechRecognizer` và `TextToSpeech` của Android qua pyjnius |
| `translator.py` | Gọi Google Translate (API chính thức hoặc bản miễn phí), có cache |
| `buildozer.spec` | Cấu hình đóng gói APK |
| `extra_manifest.xml` | Khai báo `<queries>` để Android 11 trở lên thấy dịch vụ giọng nói |
| `.github/workflows/build-apk.yml` | Build APK tự động trên GitHub, không cần máy Linux |

## Cách 1: Build APK bằng GitHub (dễ nhất, dùng được trên Windows)

1. Tạo repository mới trên GitHub và tải toàn bộ thư mục này lên, kể cả thư mục `.github`.
2. Vào tab **Actions** → chọn **Build APK** → **Run workflow**. Lần đầu mất khoảng 20–30 phút vì phải tải Android SDK/NDK; các lần sau nhanh hơn nhờ cache.
3. Khi chạy xong, tải file trong mục **Artifacts** (`phien-dich-anh-viet-apk`), giải nén ra file `.apk`.

## Cách 2: Build trên máy (Linux hoặc WSL2 trên Windows)

```bash
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool \
  pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
pip install buildozer "cython<3.1" virtualenv
cd duong-dan/toi/thu-muc-nay
buildozer -v android debug            # APK nằm trong thư mục bin/
buildozer android deploy run logcat   # nếu điện thoại đang cắm cáp và đã bật USB debugging
```

## Cài lên Samsung Galaxy S24 Ultra

1. Chép file `.apk` vào điện thoại và mở nó. Nếu máy hỏi, cho phép **Cài ứng dụng không rõ nguồn gốc** cho ứng dụng dùng để mở file (My Files hoặc Chrome).
2. Mở app và bấm **Cho phép** khi được hỏi quyền **Micro**.
3. **Thiết lập giọng nói (quan trọng):**
   - *Đọc tiếng Việt:* vào **Cài đặt → Quản lý chung → Chuyển văn bản thành giọng nói**, chọn công cụ **Google** (Speech Services by Google), rồi tải dữ liệu giọng **Tiếng Việt** và **English (US)**. Công cụ TTS của Samsung có thể không có giọng tiếng Việt.
   - *Nhận dạng giọng nói:* app dùng dịch vụ nhận dạng mặc định của máy. Nên cài và cập nhật **Google app** / **Speech Services by Google**. Nếu muốn nhận dạng cả khi mạng yếu, tải gói ngôn ngữ ngoại tuyến tiếng Việt và tiếng Anh cho Google.
4. Phần dịch luôn cần **Internet** (Wi-Fi hoặc 4G/5G).

## Dùng Google Cloud Translation API (tuỳ chọn)

Endpoint miễn phí là API không chính thức: nếu dùng nhiều có thể bị giới hạn tạm thời. Để dùng API chính thức:

1. Vào Google Cloud Console → tạo project → bật **Cloud Translation API** (cần gắn tài khoản thanh toán; mỗi tháng miễn phí 500.000 ký tự).
2. Vào **APIs & Services → Credentials → Create credentials → API key**. Nên giới hạn key chỉ dùng cho Cloud Translation API.
3. Trong app, bấm **Cài đặt**, dán key rồi bấm **Lưu**. Dòng trạng thái sẽ hiện "dịch bằng Google Cloud API".

## Chạy thử trên máy tính

```bash
pip install kivy certifi
python main.py
```

Trên máy tính chỉ dùng được phần **gõ chữ** vì nhận dạng và đọc giọng nói dùng API của Android.

## Xử lý sự cố

| Hiện tượng | Cách khắc phục |
|---|---|
| "Máy chưa có dịch vụ nhận dạng giọng nói" | Cài hoặc cập nhật Google app / Speech Services by Google |
| "Chưa có giọng đọc Tiếng Việt" | Chọn công cụ TTS là Google và tải giọng Tiếng Việt (bước 3 ở trên) |
| "Chưa cấp quyền micro" | Cài đặt → Ứng dụng → Phien dich Anh Viet → Quyền → Micro |
| "Không có kết nối mạng" | Kiểm tra Internet; nếu đang dùng bản miễn phí và bị chặn, chuyển sang API key |
| App tắt ngay khi mở | Cắm máy vào máy tính và chạy `adb logcat -s python` để xem lỗi |

Lưu ý: ô gõ chữ của Kivy có thể gõ tiếng Việt (Telex/VNI) chưa mượt với một số bàn phím. Phần giọng nói không bị ảnh hưởng.
