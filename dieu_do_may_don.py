# -*- coding: utf-8 -*-
"""Điều độ máy đơn bằng menu Terminal: FCFS, SPT, EDD, LPT, SRPT.
Chạy: python dieu_do_may_don.py

=============================================================================
GHI CHÚ (đọc trước khi chỉnh sửa):
File này là BACKEND TÍNH TOÁN thuần túy (không đổi logic so với bản gốc của
bạn). Nó được `app.py` (giao diện Streamlit) import vào để dùng, đồng thời
vẫn chạy độc lập được qua Terminal như cũ bằng lệnh phía trên.

Bố cục file (đọc theo thứ tự để dễ định vị khi cần sửa):
  A. HẰNG SỐ / SCHEMA DỮ LIỆU     -> INPUT_COLUMNS, RESULT_COLUMNS, SAMPLE_JOBS...
  B. KIỂM TRA DỮ LIỆU ĐẦU VÀO     -> validate_jobs()
  C. CÁC THUẬT TOÁN ĐIỀU ĐỘ       -> schedule_fcfs / schedule_spt / schedule_edd /
                                      schedule_lpt / schedule_srpt
  D. TÍNH KẾT QUẢ & KPI           -> calculate_job_results(), calculate_metrics()
  E. GIAO DIỆN DÒNG LỆNH (CLI)    -> chỉ dùng khi chạy trực tiếp file này,
                                      app.py KHÔNG động tới các hàm ở phần E.

  >>> Muốn thêm một luật điều độ mới: viết thêm 1 hàm schedule_xxx(jobs) ở
      mục C theo đúng khuôn dạng trả về (xem ghi chú ngay phía trên mục C),
      rồi khai báo thêm cho nó trong SCHEDULERS ở app.py (và trong biến
      `schedulers` của hàm main() bên dưới nếu muốn dùng cả ở bản Terminal).
  >>> Muốn đổi công thức KPI hiển thị ở bảng so sánh: sửa trong
      calculate_metrics() ở mục D.
=============================================================================
"""

from decimal import Decimal
from math import isfinite
from numbers import Real
from pathlib import Path
import sys

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:
    raise SystemExit(
        "Thiếu thư viện. Hãy chạy: python -m pip install pandas numpy openpyxl"
    ) from exc


# =============================================================================
# A. HẰNG SỐ / SCHEMA DỮ LIỆU
# -----------------------------------------------------------------------------
# Schema đầu vào bắt buộc: job_id, p (thời gian gia công), r (thời điểm đến),
# d (thời điểm tới hạn), w (trọng số, mặc định = 1 nếu bỏ trống).
# >>> Muốn đổi TÊN cột hay THÊM cột mới: sửa INPUT_COLUMNS/RESULT_COLUMNS/
#     DISPLAY_COLUMNS tại đây, đồng thời nhớ sửa đồng bộ ở app.py (nơi tạo
#     bảng nhập liệu st.data_editor dùng đúng các tên cột này).
# =============================================================================
INPUT_COLUMNS = ["job_id", "p", "r", "d", "w"]
RESULT_COLUMNS = INPUT_COLUMNS + [
    "start_time", "completion_time", "flow_time",
    "waiting_time", "lateness", "tardiness",
]
DISPLAY_COLUMNS = {
    "job_id": "Job ID",
    "p": "p", "r": "r", "d": "d", "w": "w",
    "start_time": "Thời điểm bắt đầu (Sⱼ)",
    "completion_time": "Thời điểm hoàn thành (Cⱼ)",
    "flow_time": "Flow time (Fⱼ = Cⱼ - rⱼ)",
    "waiting_time": "Waiting time (Wⱼ = Fⱼ - pⱼ)",
    "lateness": "Lateness (Lⱼ = Cⱼ - dⱼ)",
    "tardiness": "Tardiness (Tⱼ = max(0, Cⱼ - dⱼ))",
}
COMPARISON_COLUMNS = [
    "Luật",
    "Tổng thời gian hoàn thành",
    "Độ hữu dụng",
    "Số lượng công việc trung bình trong hệ thống",
    "Thời gian trung bình trong hệ thống",
]
RULE_METRIC_COLUMNS = [
    "Tổng thời gian gia công",
    "Tổng thời gian hoàn thành",
    "Độ hữu dụng",
    "Số lượng công việc trung bình trong hệ thống",
    "Thời gian trung bình trong hệ thống",
]
SRPT_EXTRA_COLUMNS = [
    "Thời gian hoàn thành trung bình",
    "Thời gian chờ trung bình",
    "Thời gian đáp ứng trung bình",
]
SAMPLE_JOBS = [
    {"job_id": "J1", "p": 8, "r": 0, "d": 12, "w": 2},
    {"job_id": "J2", "p": 4, "r": 1, "d": 7, "w": 1},
    {"job_id": "J3", "p": 2, "r": 2, "d": 5, "w": 3},
    {"job_id": "J4", "p": 1, "r": 4, "d": 6, "w": 2},
    {"job_id": "J5", "p": 5, "r": 6, "d": 14, "w": 1},
    {"job_id": "J6", "p": 3, "r": 9, "d": 18, "w": 2},
]


# =============================================================================
# B. KIỂM TRA DỮ LIỆU ĐẦU VÀO
# -----------------------------------------------------------------------------
# validate_jobs() là "cổng gác" duy nhất cho mọi nguồn dữ liệu (nhập tay, tải
# file, dữ liệu mẫu) trước khi đưa vào các hàm điều độ ở mục C. app.py luôn
# gọi hàm này trước khi chạy thuật toán, và bắt lỗi ValueError để hiển thị
# bằng st.error thay vì làm sập ứng dụng.
# >>> Muốn đổi điều kiện hợp lệ (vd cho phép p = 0, thêm ràng buộc cột mới...)
#     thì sửa trực tiếp trong hàm này.
# =============================================================================
def validate_jobs(jobs):
    """Kiểm tra và trả bản sao DataFrame gồm năm cột đầu vào chuẩn."""
    if not isinstance(jobs, (list, pd.DataFrame)):
        raise ValueError("Dữ liệu phải là danh sách từ điển hoặc pandas DataFrame.")
    if isinstance(jobs, list) and any(not isinstance(row, dict) for row in jobs):
        raise ValueError("Mỗi công việc phải là một từ điển.")
    df = pd.DataFrame(jobs).copy(deep=True)
    if df.empty:
        raise ValueError("Phải có ít nhất một công việc.")
    if df.columns.duplicated().any():
        raise ValueError("Tên cột không được trùng nhau.")
    missing = [col for col in INPUT_COLUMNS[:4] if col not in df.columns]
    if missing:
        raise ValueError("Thiếu cột bắt buộc: " + ", ".join(missing))

    # Mã số thuần túy được so sánh theo số; mã văn bản theo thứ tự chuỗi.
    ids = df["job_id"]
    if ids.isna().any() or ids.map(
        lambda value: not isinstance(value, (str, Real))
    ).any():
        raise ValueError("job_id phải là chuỗi hoặc số, không được bỏ trống.")
    if ids.map(lambda value: isinstance(value, Real) and (
        isinstance(value, (bool, np.bool_)) or not isfinite(value)
    )).any():
        raise ValueError("Mã công việc dạng số phải hữu hạn, không được là True/False.")
    if not ids.map(lambda value: isinstance(value, Real)).all():
        df["job_id"] = ids.astype(str).str.strip()
    if df["job_id"].map(lambda value: isinstance(value, str) and not value).any():
        raise ValueError("job_id không được rỗng hoặc chỉ chứa khoảng trắng.")
    duplicates = df.loc[df["job_id"].duplicated(keep=False), "job_id"].tolist()
    if duplicates:
        raise ValueError(f"Mã công việc bị trùng: {duplicates}")

    if "w" not in df.columns:
        df["w"] = 1
    else:
        df["w"] = df["w"].map(
            lambda value: 1 if pd.isna(value) or (
                isinstance(value, str) and not value.strip()
            ) else value
        )
    for col in ["p", "r", "d", "w"]:
        if df[col].map(lambda value: isinstance(value, (bool, np.bool_, complex))).any():
            raise ValueError(f"Cột '{col}' phải là số thực, không dùng True/False hoặc số phức.")
        numeric = pd.to_numeric(df[col], errors="coerce").astype(float)
        invalid = ~np.isfinite(numeric.to_numpy())
        if invalid.any():
            bad_ids = df.loc[invalid, "job_id"].tolist()
            raise ValueError(f"Cột '{col}' bị thiếu hoặc không phải số hữu hạn: {bad_ids}")
        df[col] = numeric

    for col, invalid, condition in [
        ("p", df["p"] <= 0, "p > 0"),
        ("r", df["r"] < 0, "r >= 0"),
        ("d", df["d"] < 0, "d >= 0"),
        ("w", df["w"] < 0, "w >= 0"),
    ]:
        if invalid.any():
            bad_ids = df.loc[invalid, "job_id"].tolist()
            raise ValueError(f"Cột '{col}' cần thỏa {condition}; công việc sai: {bad_ids}")
    return df[INPUT_COLUMNS].reset_index(drop=True)


# =============================================================================
# E. GIAO DIỆN DÒNG LỆNH (CLI) - CHỈ DÙNG KHI CHẠY TRỰC TIẾP FILE NÀY
# -----------------------------------------------------------------------------
# Toàn bộ các hàm từ đây đến hết file (input_jobs_manually, load_jobs_from_file,
# choose_rules, choose_input_data, display_rule_result, print_comparison_table,
# main, và khối `if __name__ == "__main__"`) chỉ phục vụ menu Terminal khi bạn
# chạy `python dieu_do_may_don.py` trực tiếp.
#
# app.py (Streamlit) KHÔNG import/gọi bất kỳ hàm nào trong mục E này - nó có
# phần nhập liệu & menu chọn luật riêng bằng giao diện web (sidebar, data
# editor, checkbox...). Bạn có thể an toàn xoá cả mục E nếu không còn nhu cầu
# chạy bản Terminal, mà không ảnh hưởng gì tới app Streamlit.
# =============================================================================
def input_jobs_manually():
    """Hỏi số công việc và từng trường; dữ liệu sai được yêu cầu nhập lại."""
    while True:
        try:
            count = int(input("Số lượng công việc: ").strip())
            if count <= 0:
                raise ValueError
            break
        except ValueError:
            print("Lỗi: Số lượng công việc phải là số nguyên lớn hơn 0.")

    jobs = []
    for index in range(count):
        while True:
            print(f"\nNhập công việc {index + 1}/{count}:")
            job = {
                "job_id": input("  job_id — mã công việc: ").strip(),
                "p": input("  p — thời gian gia công (> 0): ").strip(),
                "r": input("  r — thời điểm đến (>= 0): ").strip(),
                "d": input("  d — thời điểm tới hạn (>= 0): ").strip(),
                "w": input("  w — trọng số (Enter để dùng 1): ").strip(),
            }
            try:
                # Kiểm tra cùng các việc trước để phát hiện trùng mã ngay.
                validated = validate_jobs(jobs + [job])
                jobs = validated.to_dict("records")
                break
            except ValueError as exc:
                print(f"Lỗi: {exc}\nVui lòng nhập lại công việc này.")
    return validate_jobs(jobs)


def load_jobs_from_file(file_path):
    """Đọc CSV UTF-8 hoặc trang tính đầu của Excel .xlsx, rồi kiểm tra dữ liệu."""
    path = Path(str(file_path).strip().strip("\"'")).expanduser()
    if not path.is_file():
        raise ValueError(f"Không tìm thấy file: {path}")
    suffix = path.suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise ValueError("Chỉ hỗ trợ file CSV (.csv) hoặc Excel (.xlsx).")
    try:
        if suffix == ".csv":
            df = pd.read_csv(
                path, encoding="utf-8-sig", sep=None, engine="python",
                dtype={"job_id": str}, keep_default_na=False,
            )
        else:
            df = pd.read_excel(
                path, sheet_name=0, engine="openpyxl",
                dtype={"job_id": str}, keep_default_na=False,
            )
    except ImportError as exc:
        raise ValueError(
            "Thiếu bộ đọc Excel. Hãy chạy: python -m pip install openpyxl"
        ) from exc
    except Exception as exc:
        raise ValueError(
            f"Không đọc được '{path.name}'. Hãy kiểm tra định dạng, "
            f"mã hóa UTF-8 và quyền đọc file. Chi tiết: {exc}"
        ) from exc
    return validate_jobs(df)


def _prepare_jobs(jobs):
    """Chuẩn hóa dữ liệu; dùng Decimal để tính thời gian thập phân ổn định."""
    records = validate_jobs(jobs).to_dict("records")
    for job in records:
        for col in ["p", "r", "d", "w"]:
            job[col] = Decimal(str(job[col]))
    return records


# =============================================================================
# C. CÁC THUẬT TOÁN ĐIỀU ĐỘ (SCHEDULERS) - máy đơn (single machine)
# -----------------------------------------------------------------------------
# Mỗi hàm schedule_xxx(jobs) nhận dữ liệu công việc (list[dict] hoặc
# DataFrame, sẽ tự validate lại bên trong qua _prepare_jobs) và LUÔN trả về
# một dict có đúng 3 khóa:
#   - "start_times"      : {job_id: thời điểm bắt đầu chạy LẦN ĐẦU}
#   - "completion_times" : {job_id: thời điểm hoàn thành}
#   - "segments"          : list các đoạn chạy [{job_id, start, end}, ...]
#     (FCFS/SPT/EDD/LPT: mỗi job đúng 1 đoạn vì không ngắt quãng.
#      SRPT: một job có thể có NHIỀU đoạn do bị ngắt giữa chừng.)
# app.py dùng "segments" để vẽ Gantt chart (đúng cho cả trường hợp preemptive
# như SRPT) và dùng "start_times"/"completion_times" (qua calculate_job_results)
# để tính flow time, waiting time, lateness, tardiness.
#
# >>> THÊM LUẬT MỚI: copy khuôn một hàm bên dưới (ví dụ schedule_spt), đổi
#     tiêu chí sắp xếp trong dòng `min(ready, key=lambda item: (...))`, rồi
#     đăng ký hàm mới vào SCHEDULERS trong app.py để nó xuất hiện thành
#     checkbox trên giao diện.
# =============================================================================
def schedule_fcfs(jobs):
    """FCFS không ngắt: ưu tiên r nhỏ nhất, rồi job_id nhỏ nhất."""
    records = _prepare_jobs(jobs)
    ordered = sorted(records, key=lambda job: (job["r"], job["job_id"]))
    time = Decimal(0)
    starts, completions, segments = {}, {}, []
    for job in ordered:
        time = max(time, job["r"])  # Chờ nếu công việc tiếp theo chưa đến.
        jid = job["job_id"]
        starts[jid] = time
        end = time + job["p"]
        segments.append({"job_id": jid, "start": time, "end": end})
        completions[jid] = end
        time = end
    return {"start_times": starts, "completion_times": completions, "segments": segments}


def schedule_spt(jobs):
    """SPT không ngắt: chỉ chọn p nhỏ nhất trong các công việc đã đến."""
    pending = _prepare_jobs(jobs)
    time = Decimal(0)
    starts, completions, segments = {}, {}, []
    while pending:
        ready = [job for job in pending if job["r"] <= time]
        if not ready:
            time = min(job["r"] for job in pending)
            continue
        job = min(ready, key=lambda item: (item["p"], item["r"], item["job_id"]))
        jid = job["job_id"]
        starts[jid] = time
        end = time + job["p"]
        segments.append({"job_id": jid, "start": time, "end": end})
        completions[jid] = end
        time = end
        pending.remove(job)
    return {"start_times": starts, "completion_times": completions, "segments": segments}


def schedule_edd(jobs):
    """EDD không ngắt: chọn d nhỏ nhất trong các công việc đã đến."""
    pending = _prepare_jobs(jobs)
    time = Decimal(0)
    starts, completions, segments = {}, {}, []
    while pending:
        ready = [job for job in pending if job["r"] <= time]
        if not ready:
            time = min(job["r"] for job in pending)
            continue
        job = min(ready, key=lambda item: (item["d"], item["r"], item["job_id"]))
        jid = job["job_id"]
        starts[jid] = time
        end = time + job["p"]
        segments.append({"job_id": jid, "start": time, "end": end})
        completions[jid] = end
        time = end
        pending.remove(job)
    return {"start_times": starts, "completion_times": completions, "segments": segments}


def schedule_lpt(jobs):
    """LPT không ngắt: chọn p lớn nhất; khi bằng nhau xét r rồi job_id."""
    pending = _prepare_jobs(jobs)
    time = Decimal(0)
    starts, completions, segments = {}, {}, []
    while pending:
        ready = [job for job in pending if job["r"] <= time]
        if not ready:
            time = min(job["r"] for job in pending)
            continue
        job = min(ready, key=lambda item: (-item["p"], item["r"], item["job_id"]))
        jid = job["job_id"]
        starts[jid] = time
        end = time + job["p"]
        segments.append({"job_id": jid, "start": time, "end": end})
        completions[jid] = end
        time = end
        pending.remove(job)
    return {"start_times": starts, "completion_times": completions, "segments": segments}


def schedule_srpt(jobs):
    """SRPT có ngắt: luôn ưu tiên phần thời gian gia công còn lại nhỏ nhất."""
    records = _prepare_jobs(jobs)
    remaining = {job["job_id"]: job["p"] for job in records}
    time = Decimal(0)
    starts, completions, segments = {}, {}, []
    current = None
    while len(completions) < len(records):
        pending = [job for job in records if remaining[job["job_id"]] > 0]
        ready = [job for job in pending if job["r"] <= time]
        if not ready:
            time = min(job["r"] for job in pending)
            current = None
            continue

        candidate = min(
            ready, key=lambda job: (remaining[job["job_id"]], job["r"], job["job_id"])
        )
        if current is None:
            current = candidate
        elif remaining[candidate["job_id"]] < remaining[current["job_id"]]:
            current = candidate  # Chỉ ngắt khi phần còn lại NHỎ HƠN nghiêm ngặt.
        jid = current["job_id"]
        starts.setdefault(jid, time)  # Không ghi đè lần bắt đầu đầu tiên.
        finish = time + remaining[jid]
        arrivals = [job["r"] for job in pending if job["r"] > time]
        end = min(finish, min(arrivals)) if arrivals else finish
        remaining[jid] -= end - time

        # Một công việc vẫn chạy qua sự kiện đến thì gộp đoạn, không tạo ngắt giả.
        if segments and segments[-1]["job_id"] == jid and segments[-1]["end"] == time:
            segments[-1]["end"] = end
        else:
            segments.append({"job_id": jid, "start": time, "end": end})
        time = end
        if remaining[jid] == 0:
            completions[jid] = time
            current = None
    return {"start_times": starts, "completion_times": completions, "segments": segments}


# =============================================================================
# D. TÍNH KẾT QUẢ CHI TIẾT & KPI TỔNG HỢP
# -----------------------------------------------------------------------------
# calculate_job_results(): từ 1 kết quả schedule_xxx(), tạo bảng chi tiết mỗi
#   công việc 1 dòng (start_time, completion_time, flow_time, waiting_time,
#   lateness, tardiness). Đây là bảng app.py hiển thị trong phần "Chi tiết
#   lịch trình" và cũng là nguồn để vẽ Gantt/tính tardiness.
#   >>> Muốn đổi CÔNG THỨC (vd định nghĩa lateness/tardiness khác) sửa ở đây.
#
# calculate_metrics(): tính 5 KPI tổng hợp theo đúng quy ước môn học (Tổng
#   thời gian gia công, Tổng thời gian hoàn thành, Độ hữu dụng, Số lượng công
#   việc trung bình trong hệ thống, Thời gian trung bình trong hệ thống) +
#   3 chỉ số riêng cho SRPT. Đây là bảng "so sánh chuẩn" app.py hiển thị.
#   >>> Muốn đổi CÔNG THỨC KPI hiển thị ở bảng so sánh chính: sửa ở đây.
# =============================================================================
def calculate_job_results(jobs, schedule_result):
    """Từ lịch của một luật, tạo một dòng kết quả cho mỗi công việc."""
    records = _prepare_jobs(jobs)
    if not isinstance(schedule_result, dict) or not {
        "start_times", "completion_times", "segments"
    }.issubset(schedule_result):
        raise ValueError("Kết quả điều độ phải có thời điểm bắt đầu, hoàn thành và các đoạn chạy.")
    starts = schedule_result["start_times"]
    completions = schedule_result["completion_times"]
    expected_ids = {job["job_id"] for job in records}
    if set(starts) != expected_ids or set(completions) != expected_ids:
        raise ValueError("Mã công việc trong lịch không khớp với dữ liệu đầu vào.")

    rows = []
    # Mỗi việc một dòng, theo lần đầu được máy gia công.
    for job in sorted(records, key=lambda item: starts[item["job_id"]]):
        jid = job["job_id"]
        start = Decimal(str(starts[jid]))
        completion = Decimal(str(completions[jid]))
        flow = completion - job["r"]
        lateness = completion - job["d"]
        row = {"job_id": jid, **{col: float(job[col]) for col in ["p", "r", "d", "w"]}}
        row.update(
            start_time=float(start), completion_time=float(completion),
            flow_time=float(flow), waiting_time=float(flow - job["p"]),
            lateness=float(lateness), tardiness=float(max(Decimal(0), lateness)),
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


def calculate_metrics(result_df, rule_name):
    """Tính các KPI tổng hợp chung của năm luật theo công thức môn học."""
    if rule_name not in {"FCFS", "SPT", "EDD", "LPT", "SRPT"}:
        raise ValueError("Tên luật không hợp lệ.")
    if not isinstance(result_df, pd.DataFrame) or result_df.empty:
        raise ValueError("Bảng kết quả phải là DataFrame không rỗng.")

    required = ["p", "r", "completion_time"]
    missing = [col for col in required if col not in result_df.columns]
    if missing:
        raise ValueError("Bảng kết quả thiếu cột: " + ", ".join(missing))
    data = result_df[required].apply(pd.to_numeric, errors="coerce").astype(float)
    if not np.isfinite(data.to_numpy()).all():
        raise ValueError("Các cột tính KPI phải chứa số hữu hạn.")

    n = len(data)
    system_time = data["completion_time"] - data["r"]
    if (data["p"] <= 0).any() or (system_time <= 0).any():
        raise ValueError("Thời gian gia công và thời gian trong hệ thống phải lớn hơn 0.")
    total_processing_time = float(data["p"].sum())
    total_completion_time = float(system_time.sum())
    if not np.isfinite([total_processing_time, total_completion_time]).all():
        raise ValueError("Tổng thời gian quá lớn; không thể tính KPI hữu hạn.")

    # Quy ước môn học: tổng thời gian hoàn thành là tổng (C_j - r_j).
    utilization = total_processing_time / total_completion_time
    average_jobs_in_system = total_completion_time / total_processing_time
    average_time_in_system = total_completion_time / n
    metrics = {
        "Luật": rule_name,
        "Tổng thời gian gia công": total_processing_time,
        "Tổng thời gian hoàn thành": total_completion_time,
        "Độ hữu dụng": utilization,
        "Số lượng công việc trung bình trong hệ thống": average_jobs_in_system,
        "Thời gian trung bình trong hệ thống": average_time_in_system,
    }

    return metrics


def _format_time(value):
    """In thời gian gọn, không làm thay đổi số dùng trong tính toán."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_machine_order(schedule_result):
    """In các đoạn chạy theo thời gian, giữ mã lặp và bổ sung khoảng máy chờ."""
    parts = []
    previous_end = Decimal(0)
    for segment in schedule_result["segments"]:
        start, end = segment["start"], segment["end"]
        if start > previous_end:
            parts.append(f"Chờ ({_format_time(previous_end)}–{_format_time(start)})")
        parts.append(
            f"{segment['job_id']} ({_format_time(start)}–{_format_time(end)})"
        )
        previous_end = end
    return " → ".join(parts)


def choose_rules():
    """Menu chọn một, nhiều hoặc tất cả luật; giữ thứ tự lựa chọn của người dùng."""
    options = {"1": "FCFS", "2": "SPT", "3": "EDD", "4": "LPT", "5": "SRPT"}
    print("\nCHỌN LUẬT ĐIỀU ĐỘ")
    for number, name in options.items():
        print(f"{number}. {name}")
    print("6. Chạy tất cả luật")
    while True:
        tokens = [part.strip() for part in input("Chọn luật (ví dụ 1,3,5 hoặc 6): ").split(",")]
        if tokens == ["6"]:
            return list(options.values())
        if tokens and all(token in options for token in tokens):
            return list(dict.fromkeys(options[token] for token in tokens))
        print("Lỗi: Nhập số từ 1 đến 5, ngăn cách bằng dấu phẩy; hoặc nhập riêng 6.")


def choose_input_data():
    """Chọn nhập tay, đọc CSV/Excel hoặc dùng mẫu; cho chọn lại nếu đọc sai."""
    while True:
        print("\nCHỌN CÁCH NHẬP DỮ LIỆU")
        print("1. Nhập thủ công từ bàn phím")
        print("2. Đọc từ file CSV")
        print("3. Đọc từ file Excel (.xlsx)")
        print("4. Chạy thử bộ dữ liệu mẫu 6 công việc")
        choice = input("Chọn cách nhập (1–4): ").strip()
        if choice == "1":
            return input_jobs_manually()
        if choice == "4":
            return validate_jobs(SAMPLE_JOBS)
        if choice not in {"2", "3"}:
            print("Lỗi: Vui lòng chọn 1, 2, 3 hoặc 4.")
            continue
        print("File cần các cột: job_id, p, r, d, w; thiếu w hoặc để trống w thì dùng 1.")
        print("Yêu cầu: p > 0; r, d, w >= 0; job_id không trùng. CSV dùng UTF-8.")
        path = input("Nhập đường dẫn file: ").strip().strip("\"'")
        expected_suffix = ".csv" if choice == "2" else ".xlsx"
        if Path(path).suffix.lower() != expected_suffix:
            print(f"Lỗi: Lựa chọn này cần file {expected_suffix}. Vui lòng chọn và nhập lại.")
            continue
        try:
            return load_jobs_from_file(path)
        except ValueError as exc:
            print(f"Lỗi: {exc}\nVui lòng chọn cách nhập và thử lại.")


def calculate_srpt_job_times(result_df):
    """Tạo đúng một dòng cho mỗi công việc SRPT, dùng lần bắt đầu đầu tiên."""
    return pd.DataFrame({
        "Job ID": result_df["job_id"].to_numpy(),
        "Thời gian hoàn thành": (result_df["completion_time"] - result_df["r"]).to_numpy(),
        "Thời gian chờ": (
            result_df["completion_time"] - result_df["r"] - result_df["p"]
        ).to_numpy(),
        "Thời gian đáp ứng": (
            result_df["start_time"] - result_df["r"]
        ).to_numpy(),
    })


def display_rule_result(rule_name, jobs, scheduler):
    """In kết quả từng luật; SRPT có thêm bảng thời gian theo công việc."""
    schedule = scheduler(jobs)
    result = calculate_job_results(jobs, schedule)
    metrics = calculate_metrics(result, rule_name)
    print("\n" + "=" * 80)
    print(f"KẾT QUẢ LUẬT {rule_name}")
    print("\nA. THỨ TỰ MÁY CHẠY")
    print("Thứ tự máy chạy:", format_machine_order(schedule))
    print("\nB. BẢNG KẾT QUẢ CHI TIẾT (theo lần bắt đầu chạy, mỗi công việc một dòng)")
    print(result.rename(columns=DISPLAY_COLUMNS).to_string(
        index=False, float_format=lambda value: f"{value:.6g}"
    ))
    if rule_name == "SRPT":
        job_times = calculate_srpt_job_times(result)
        print("\nBẢNG THỜI GIAN CỦA TỪNG CÔNG VIỆC – SRPT")
        print(job_times.to_string(
            index=False,
            formatters={
                column: _format_table_time
                for column in job_times.columns if column != "Job ID"
            },
        ))
    print("\nC. BẢNG CHỈ SỐ RIÊNG")
    metric_columns = RULE_METRIC_COLUMNS
    metric_rows = [
        {
            "Chỉ số": key,
            "Giá trị": f"{metrics[key]:.2%}" if key == "Độ hữu dụng"
            else f"{metrics[key]:.2f}",
        }
        for key in metric_columns
    ]
    print(pd.DataFrame(metric_rows).to_string(index=False))
    plot_gantt(schedule["segments"], rule_name)
    return metrics


def print_comparison_table(metrics_rows):
    """In bảng so sánh cuối có đúng năm cột và hai chữ số thập phân."""
    comparison = pd.DataFrame(metrics_rows).reindex(columns=COMPARISON_COLUMNS)
    print(comparison.to_string(
        index=False,
        float_format=lambda value: f"{value:.2f}",
        formatters={"Độ hữu dụng": lambda value: f"{value:.2%}"},
    ))
    return comparison


def main():
    """Chạy menu Terminal, mô phỏng các luật đã chọn và in bảng so sánh 5 cột."""
    schedulers = {
        "FCFS": schedule_fcfs, "SPT": schedule_spt, "EDD": schedule_edd,
        "LPT": schedule_lpt, "SRPT": schedule_srpt,
    }
    try:
        print("CHƯƠNG TRÌNH ĐIỀU ĐỘ MÁY ĐƠN")
        selected = choose_rules()
        jobs = choose_input_data()
        print("\nDỮ LIỆU SỬ DỤNG")
        print(jobs.to_string(index=False, float_format=lambda value: f"{value:.6g}"))
        metrics = [
            display_rule_result(name, jobs, schedulers[name]) for name in selected
        ]
        # Chỉ in một bảng so sánh cuối, kể cả khi người dùng chọn một luật.
        print("\nBẢNG SO SÁNH CÁC LUẬT ĐÃ CHỌN")
        print_comparison_table(metrics)
        print("\nĐã hoàn tất. Chạy lại chương trình nếu muốn đổi luật hoặc dữ liệu.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nĐã dừng nhập dữ liệu. Bạn có thể chạy lại chương trình trong Terminal.")
        return 0
    except ValueError as exc:
        print(f"\nLỗi: {exc}\nVui lòng kiểm tra dữ liệu và chạy lại chương trình.")
        return 1


if __name__ == "__main__":
    # Cấu hình đầu ra để Terminal Windows hiển thị tiếng Việt và dấu mũi tên.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
