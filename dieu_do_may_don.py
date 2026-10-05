# -*- coding: utf-8 -*-
"""Thuật toán điều độ máy đơn: FCFS, SPT, EDD, LPT (không ngắt) và SRPT (có ngắt).

File này chỉ chứa phần tính toán; giao diện nằm ở app.py.
"""

from decimal import Decimal
from math import isfinite
from numbers import Real

import numpy as np
import pandas as pd

INPUT_COLUMNS = ["job_id", "p", "r", "d", "w"]
RESULT_COLUMNS = INPUT_COLUMNS + [
    "start_time", "completion_time", "flow_time",
    "waiting_time", "lateness", "tardiness",
]
DISPLAY_COLUMNS = {
    "job_id": "Job ID",
    "p": "p", "r": "r", "d": "d", "w": "w",
    "start_time": "Thời điểm bắt đầu S_j",
    "completion_time": "Thời điểm hoàn thành C_j",
    "flow_time": "Flow time F_j = C_j - r_j",
    "waiting_time": "Waiting time W_j = F_j - p_j",
    "lateness": "Lateness L_j = C_j - d_j",
    "tardiness": "Tardiness T_j = max(0, C_j - d_j)",
}
COMPARISON_COLUMNS = [
    "Luật",
    "Tổng thời gian hoàn thành",
    "Độ hữu dụng",
    "Số lượng công việc trung bình trong hệ thống",
    "Thời gian trung bình trong hệ thống",
]
SAMPLE_JOBS = [
    {"job_id": "J1", "p": 8, "r": 0, "d": 12, "w": 2},
    {"job_id": "J2", "p": 4, "r": 1, "d": 7, "w": 1},
    {"job_id": "J3", "p": 2, "r": 2, "d": 5, "w": 3},
    {"job_id": "J4", "p": 1, "r": 4, "d": 6, "w": 2},
    {"job_id": "J5", "p": 5, "r": 6, "d": 14, "w": 1},
    {"job_id": "J6", "p": 3, "r": 9, "d": 18, "w": 2},
]


# --------------------------------------------------------------------------
# Kiểm tra dữ liệu đầu vào
# --------------------------------------------------------------------------
def validate_jobs(jobs):
    """Kiểm tra và trả bản sao DataFrame gồm năm cột đầu vào chuẩn."""
    if not isinstance(jobs, (list, pd.DataFrame)):
        raise ValueError("Dữ liệu phải là danh sách từ điển hoặc pandas DataFrame.")
    if isinstance(jobs, list) and not all(isinstance(row, dict) for row in jobs):
        raise ValueError("Mỗi công việc phải là một từ điển.")
    df = pd.DataFrame(jobs).copy(deep=True)
    if df.empty:
        raise ValueError("Phải có ít nhất một công việc.")
    if df.columns.duplicated().any():
        raise ValueError("Tên cột không được trùng nhau.")
    missing = [col for col in INPUT_COLUMNS[:4] if col not in df.columns]
    if missing:
        raise ValueError("Thiếu cột bắt buộc: " + ", ".join(missing))

    # job_id: chuỗi hoặc số hữu hạn; nếu có chuỗi thì quy hết về chuỗi đã cắt khoảng trắng.
    ids = df["job_id"]
    if ids.isna().any() or not ids.map(lambda v: isinstance(v, (str, Real))).all():
        raise ValueError("job_id phải là chuỗi hoặc số, không được bỏ trống.")
    if ids.map(lambda v: isinstance(v, Real) and (
        isinstance(v, (bool, np.bool_)) or not isfinite(v)
    )).any():
        raise ValueError("Mã công việc dạng số phải hữu hạn, không được là True/False.")
    if not ids.map(lambda v: isinstance(v, Real)).all():
        df["job_id"] = ids.astype(str).str.strip()
    if df["job_id"].map(lambda v: isinstance(v, str) and not v).any():
        raise ValueError("job_id không được rỗng hoặc chỉ chứa khoảng trắng.")
    duplicates = df.loc[df["job_id"].duplicated(keep=False), "job_id"].tolist()
    if duplicates:
        raise ValueError(f"Mã công việc bị trùng: {duplicates}")

    # w thiếu hoặc để trống thì dùng 1.
    if "w" not in df.columns:
        df["w"] = 1
    else:
        df["w"] = df["w"].map(
            lambda v: 1 if pd.isna(v) or (isinstance(v, str) and not v.strip()) else v
        )

    for col in ["p", "r", "d", "w"]:
        if df[col].map(lambda v: isinstance(v, (bool, np.bool_, complex))).any():
            raise ValueError(f"Cột '{col}' phải là số thực, không dùng True/False hoặc số phức.")
        numeric = pd.to_numeric(df[col], errors="coerce").astype(float)
        invalid = ~np.isfinite(numeric.to_numpy())
        if invalid.any():
            raise ValueError(
                f"Cột '{col}' bị thiếu hoặc không phải số hữu hạn: {df.loc[invalid, 'job_id'].tolist()}"
            )
        df[col] = numeric

    for col, bad, condition in [
        ("p", df["p"] <= 0, "p > 0"),
        ("r", df["r"] < 0, "r >= 0"),
        ("d", df["d"] < 0, "d >= 0"),
        ("w", df["w"] < 0, "w >= 0"),
    ]:
        if bad.any():
            raise ValueError(
                f"Cột '{col}' cần thỏa {condition}; công việc sai: {df.loc[bad, 'job_id'].tolist()}"
            )
    return df[INPUT_COLUMNS].reset_index(drop=True)


def _prepare_jobs(jobs):
    """Chuẩn hóa dữ liệu; dùng Decimal để tính thời gian thập phân ổn định."""
    records = validate_jobs(jobs).to_dict("records")
    for job in records:
        for col in ("p", "r", "d", "w"):
            job[col] = Decimal(str(job[col]))
    return records


# --------------------------------------------------------------------------
# Các luật điều độ
# --------------------------------------------------------------------------
# Khóa ưu tiên của các luật không ngắt: giá trị nhỏ hơn được chạy trước.
_PRIORITY = {
    "FCFS": lambda j: (j["r"], j["job_id"]),
    "SPT": lambda j: (j["p"], j["r"], j["job_id"]),
    "EDD": lambda j: (j["d"], j["r"], j["job_id"]),
    "LPT": lambda j: (-j["p"], j["r"], j["job_id"]),
}


def _schedule_nonpreemptive(jobs, key):
    """Luật không ngắt: mỗi lần chọn việc ưu tiên nhất trong các việc đã đến."""
    pending = _prepare_jobs(jobs)
    time = Decimal(0)
    starts, completions, segments = {}, {}, []
    while pending:
        ready = [job for job in pending if job["r"] <= time]
        if not ready:  # Máy chờ đến khi có việc mới.
            time = min(job["r"] for job in pending)
            continue
        job = min(ready, key=key)
        jid, end = job["job_id"], time + job["p"]
        starts[jid], completions[jid] = time, end
        segments.append({"job_id": jid, "start": time, "end": end})
        time = end
        pending.remove(job)
    return {"start_times": starts, "completion_times": completions, "segments": segments}


def schedule_fcfs(jobs):
    """FCFS: ưu tiên r nhỏ nhất, rồi job_id nhỏ nhất."""
    return _schedule_nonpreemptive(jobs, _PRIORITY["FCFS"])


def schedule_spt(jobs):
    """SPT: ưu tiên p nhỏ nhất."""
    return _schedule_nonpreemptive(jobs, _PRIORITY["SPT"])


def schedule_edd(jobs):
    """EDD: ưu tiên d nhỏ nhất."""
    return _schedule_nonpreemptive(jobs, _PRIORITY["EDD"])


def schedule_lpt(jobs):
    """LPT: ưu tiên p lớn nhất."""
    return _schedule_nonpreemptive(jobs, _PRIORITY["LPT"])


def schedule_srpt(jobs):
    """SRPT có ngắt: luôn ưu tiên việc có thời gian gia công còn lại nhỏ nhất."""
    records = _prepare_jobs(jobs)
    remaining = {job["job_id"]: job["p"] for job in records}
    time = Decimal(0)
    starts, completions, segments = {}, {}, []
    current = None
    while len(completions) < len(records):
        pending = [job for job in records if remaining[job["job_id"]] > 0]
        ready = [job for job in pending if job["r"] <= time]
        if not ready:
            time, current = min(job["r"] for job in pending), None
            continue

        best = min(ready, key=lambda j: (remaining[j["job_id"]], j["r"], j["job_id"]))
        # Chỉ ngắt khi phần còn lại NHỎ HƠN nghiêm ngặt.
        if current is None or remaining[best["job_id"]] < remaining[current["job_id"]]:
            current = best
        jid = current["job_id"]
        starts.setdefault(jid, time)  # Giữ lần bắt đầu đầu tiên.

        next_arrivals = [job["r"] for job in pending if job["r"] > time]
        end = min([time + remaining[jid], *next_arrivals])
        remaining[jid] -= end - time

        # Việc vẫn chạy qua sự kiện đến thì gộp đoạn, không tạo ngắt giả.
        if segments and segments[-1]["job_id"] == jid and segments[-1]["end"] == time:
            segments[-1]["end"] = end
        else:
            segments.append({"job_id": jid, "start": time, "end": end})
        time = end
        if remaining[jid] == 0:
            completions[jid], current = time, None
    return {"start_times": starts, "completion_times": completions, "segments": segments}


# --------------------------------------------------------------------------
# Kết quả và chỉ số
# --------------------------------------------------------------------------
def calculate_job_results(jobs, schedule_result):
    """Từ lịch của một luật, tạo một dòng kết quả cho mỗi công việc."""
    records = _prepare_jobs(jobs)
    starts = schedule_result["start_times"]
    completions = schedule_result["completion_times"]
    ids = {job["job_id"] for job in records}
    if set(starts) != ids or set(completions) != ids:
        raise ValueError("Mã công việc trong lịch không khớp với dữ liệu đầu vào.")

    rows = []
    for job in sorted(records, key=lambda item: starts[item["job_id"]]):
        jid = job["job_id"]
        completion = Decimal(str(completions[jid]))
        flow = completion - job["r"]
        lateness = completion - job["d"]
        rows.append({
            "job_id": jid,
            **{col: float(job[col]) for col in ("p", "r", "d", "w")},
            "start_time": float(Decimal(str(starts[jid]))),
            "completion_time": float(completion),
            "flow_time": float(flow),
            "waiting_time": float(flow - job["p"]),
            "lateness": float(lateness),
            "tardiness": float(max(Decimal(0), lateness)),
        })
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


def calculate_metrics(result_df, rule_name):
    """Các KPI tổng hợp của một luật. Tổng thời gian hoàn thành = tổng (C_j - r_j)."""
    total_p = float(result_df["p"].sum())
    total_c = float((result_df["completion_time"] - result_df["r"]).sum())
    return {
        "Luật": rule_name,
        "Tổng thời gian gia công": total_p,
        "Tổng thời gian hoàn thành": total_c,
        "Độ hữu dụng": total_p / total_c,
        "Số lượng công việc trung bình trong hệ thống": total_c / total_p,
        "Thời gian trung bình trong hệ thống": total_c / len(result_df),
    }


def calculate_srpt_job_times(result_df):
    """Một dòng mỗi công việc: thời gian hoàn thành, chờ và đáp ứng (theo lần chạy đầu tiên)."""
    return pd.DataFrame({
        "Job ID": result_df["job_id"].to_numpy(),
        "Thời gian hoàn thành": result_df["flow_time"].to_numpy(),
        "Thời gian chờ": result_df["waiting_time"].to_numpy(),
        "Thời gian đáp ứng": (result_df["start_time"] - result_df["r"]).to_numpy(),
    })


def _format_time(value):
    """In thời gian gọn, không làm thay đổi số dùng trong tính toán."""
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_machine_order(schedule_result):
    """Các đoạn chạy theo thời gian, giữ mã lặp và bổ sung khoảng máy chờ."""
    parts, previous_end = [], Decimal(0)
    for seg in schedule_result["segments"]:
        if seg["start"] > previous_end:
            parts.append(f"Idle ({_format_time(previous_end)}–{_format_time(seg['start'])})")
        parts.append(f"{seg['job_id']} ({_format_time(seg['start'])}–{_format_time(seg['end'])})")
        previous_end = seg["end"]
    return " → ".join(parts)
