# -*- coding: utf-8 -*-
"""
=============================================================================
  APP STREAMLIT - ĐIỀU ĐỘ MÁY ĐƠN (SINGLE MACHINE SCHEDULING)
=============================================================================
File này CHỈ LÀ GIAO DIỆN (UI). Toàn bộ thuật toán điều độ (FCFS, SPT, EDD, LPT, SRPT), công thức KPI và validate dữ liệu nằm ở file `dieu_do_may_don.py` 

Chạy ứng dụng:
    pip install streamlit pandas numpy plotly openpyxl
    streamlit run app.py

Bố cục file:
    1. IMPORT BACKEND & CONFIG TRANG
    2. ĐỌC FILE NGƯỜI DÙNG TẢI LÊN
    3. HÀM VẼ GANTT CHART
    4. GIAO DIỆN: SIDEBAR
    5. GIAO DIỆN: BẢNG NHẬP LIỆU
    6. GIAO DIỆN: KẾT QUẢ
    7. GIAO DIỆN: GANTT CHART
    8. HÀM main() - ĐIỀU PHỐI TOÀN BỘ LUỒNG CHẠY
=============================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import timedelta, datetime

# -----------------------------------------------------------------------------
# 1. IMPORT BACKEND & CONFIG TRANG
# -----------------------------------------------------------------------------
# >>> Toàn bộ hàm dưới đây được định nghĩa trong dieu_do_may_don.py.
#     KHÔNG sửa logic của chúng ở file này - muốn đổi thuật toán/công thức KPI thì mở dieu_do_may_don.py (đã có chú thích từng mục A-E trong đó).
import dieu_do_may_don as backend

st.set_page_config(page_title="Điều độ máy đơn", layout="wide")

# Đăng ký các luật điều độ sẽ hiển thị thành checkbox trên giao diện.
# key   = mã luật (dùng nội bộ, trùng với "rule_name" mà backend yêu cầu)
# value = hàm scheduler tương ứng bên backend
# >>> THÊM LUẬT MỚI: viết hàm schedule_xxx() trong dieu_do_may_don.py (mục C),
#     rồi thêm 1 dòng vào dict này -> checkbox sẽ tự xuất hiện, không cần sửa
#     gì thêm ở phần UI phía dưới.
SCHEDULERS = {
    "FCFS": backend.schedule_fcfs,
    "SPT": backend.schedule_spt,
    "EDD": backend.schedule_edd,
    "LPT": backend.schedule_lpt,
    "SRPT": backend.schedule_srpt,
}
RULE_FULL_NAME = {
    "FCFS": "FCFS/FIFO - First Come First Served",
    "SPT": "SPT - Shortest Processing Time",
    "EDD": "EDD - Earliest Due Date",
    "LPT": "LPT - Longest Processing Time",
    "SRPT": "SRPT - Shortest Remaining Processing Time",
}

# Đơn vị p/r/d trong dữ liệu được coi là GIỜ tính từ mốc này.
MACHINE_LABEL = "Máy đơn"


# -----------------------------------------------------------------------------
# 2. ĐỌC FILE NGƯỜI DÙNG TẢI LÊN
# -----------------------------------------------------------------------------
# Bản gốc backend.load_jobs_from_file() nhận ĐƯỜNG DẪN file trên ổ đĩa (dùng
# cho Terminal). Trên web, Streamlit đưa file dưới dạng buffer trong bộ nhớ
# (UploadedFile), nên cần một hàm đọc riêng - nhưng vẫn gọi lại đúng
# backend.validate_jobs() để không lặp lại logic kiểm tra dữ liệu.
# >>> Muốn hỗ trợ thêm định dạng file khác: thêm nhánh elif ở đây.
def read_uploaded_jobs(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        raw_df = pd.read_csv(uploaded_file, dtype={"job_id": str}, keep_default_na=False)
    elif name.endswith((".xlsx", ".xls")):
        raw_df = pd.read_excel(uploaded_file, sheet_name=0, dtype={"job_id": str},
                                keep_default_na=False)
    else:
        raise ValueError("Chỉ hỗ trợ file CSV (.csv) hoặc Excel (.xlsx).")
    # validate_jobs() là hàm CHUẨN của backend -> đảm bảo file tải lên tuân
    # thủ đúng schema job_id, p, r, d, w như dữ liệu nhập tay/dữ liệu mẫu.
    return backend.validate_jobs(raw_df)


# -----------------------------------------------------------------------------
# 3. HÀM VẼ GANTT CHART (DẠNG TRỤC SỐ THUẦN TÚY)
# -----------------------------------------------------------------------------
def plot_gantt_chart(schedule_result: dict, result_df: pd.DataFrame, rule_key: str):
    segments = schedule_result["segments"]
    seg_df = pd.DataFrame([
        {
            "Job": seg["job_id"],
            "Start": float(seg["start"]),
            "End": float(seg["end"]),
            "Duration": float(seg["end"]) - float(seg["start"]),
        }
        for seg in segments
    ])
    
    # Gắn thêm thông tin p, r, d, tardiness để hiện tooltip
    seg_df = seg_df.merge(
        result_df[["job_id", "p", "r", "d", "tardiness", "completion_time"]],
        left_on="Job", right_on="job_id", how="left",
    )
    seg_df["Machine"] = MACHINE_LABEL
    seg_df["Trạng thái"] = np.where(seg_df["tardiness"] > 0, "Trễ hạn", "Đúng hạn")

    # Dùng px.bar để vẽ biểu đồ thanh ngang dạng trục số (0, 2, 4, 6...)
    fig = px.bar(
        seg_df,
        x="Duration",
        y="Machine",
        base="Start",
        color="Job",
        pattern_shape="Trạng thái",
        pattern_shape_map={"Trễ hạn": "/", "Đúng hạn": ""},
        orientation="h",
        hover_data={
            "Job": True, "Start": ":.2f", "End": ":.2f",
            "Duration": False, "Machine": False,
            "p": ":.2f", "r": ":.2f", "d": ":.2f", "tardiness": ":.2f",
        },
        title=f"Luật điều độ: {RULE_FULL_NAME.get(rule_key, rule_key)}",
    )
    
    # Tinh chỉnh lại trục X hiển thị dạng số giờ rõ ràng
    fig.update_xaxes(title="Thời gian (Giờ)", tickformat=".1f")
    fig.update_yaxes(title="")
    fig.update_layout(height=260, legend_title="Job", font=dict(size=13))
    
    return fig

# -----------------------------------------------------------------------------
# 4. GIAO DIỆN: SIDEBAR
# -----------------------------------------------------------------------------
def sidebar_ui():
    st.sidebar.header("⚙️ Cấu hình điều độ")

    st.sidebar.subheader("1️⃣ Nguồn dữ liệu công việc")
    input_method = st.sidebar.radio(
        "Chọn cách nhập dữ liệu",
        ["📊 Nhập thủ công", "📁 Tải file CSV/Excel"],
        label_visibility="collapsed",
    )

    if input_method == "📁 Tải file CSV/Excel":
        uploaded_file = st.sidebar.file_uploader("Chọn file (.csv, .xlsx)",
                                                   type=["csv", "xlsx", "xls"])
        if uploaded_file is not None:
            sig = f"{uploaded_file.name}-{uploaded_file.size}"
            if sig != st.session_state.get("last_uploaded_sig"):
                try:
                    validated_df = read_uploaded_jobs(uploaded_file)
                    st.session_state.df = validated_df
                    st.session_state.editor_version += 1
                    st.session_state.last_uploaded_sig = sig
                    st.sidebar.success(f"✅ Đã tải {len(validated_df)} công việc hợp lệ.")
                except ValueError as exc:
                    st.sidebar.error(f"❌ File không hợp lệ: {exc}")
                except Exception as exc:
                    st.sidebar.error(f"❌ Lỗi khi đọc file: {exc}")

        with st.sidebar.expander("ℹ️ Cấu trúc file yêu cầu"):
            st.write("**Cột bắt buộc:** job_id, p, r, d")
            st.write("**Cột tùy chọn:** w (trọng số, mặc định = 1 nếu để trống)")
            st.caption("p > 0 ; r, d, w ≥ 0 ; job_id không được trùng.")

    if st.sidebar.button("🔄 Reset"):
        st.session_state.df = backend.validate_jobs(backend.SAMPLE_JOBS)
        st.session_state.editor_version += 1
        st.session_state.last_uploaded_sig = None
        st.session_state.results = {}
        st.rerun()


    st.sidebar.divider()
    st.sidebar.subheader("2️⃣ Chọn luật điều độ")
    
    # Hàm tự động cập nhật trạng thái cho tất cả các checkbox con khi bấm "Chọn tất cả"
    def toggle_all_rules():
        val = st.session_state.get("select_all_master", True)
        for key in SCHEDULERS:
            st.session_state[f"chk_{key}"] = val
    
    # Checkbox tổng "Chọn tất cả" ở trên cùng
    st.sidebar.checkbox("Chọn tất cả", value=True, key="select_all_master", on_change=toggle_all_rules)
    
    # Đảm bảo các checkbox con có giá trị khởi tạo trong session_state
    for key in SCHEDULERS:
        chk_key = f"chk_{key}"
        if chk_key not in st.session_state:
            st.session_state[chk_key] = True
    
    # Tạo danh sách các checkbox cho từng luật
    selected_rules = [
        key for key in SCHEDULERS
        if st.sidebar.checkbox(RULE_FULL_NAME[key], key=f"chk_{key}")
    ]


    st.sidebar.divider()
    run_clicked = st.sidebar.button("🚀 Điều độ", type="primary",
                                     use_container_width=True)
    return selected_rules, run_clicked


# -----------------------------------------------------------------------------
# 6. GIAO DIỆN: BẢNG NHẬP LIỆU
# -----------------------------------------------------------------------------
def input_section_ui() -> pd.DataFrame:
    st.subheader("Dữ liệu công việc")
    st.caption("Nhấn dấu `+` cuối bảng để thêm dòng, chọn dòng rồi nhấn Delete để xóa.")
    edited_df = st.data_editor(
        st.session_state.df,
        num_rows="dynamic",
        use_container_width=True,
        key=f"data_editor_{st.session_state.editor_version}",
        column_config={
            "job_id": st.column_config.TextColumn("J (công việc)", required=True), 
            "p": st.column_config.NumberColumn("p (thời gian gia công)", min_value=0.01,
                                               step=0.5, required=True),
            "r": st.column_config.NumberColumn("r (thời gian đến)", min_value=0.0, step=0.5,
                                               required=True),
            "d": st.column_config.NumberColumn("d (thời gian tới hạn)", min_value=0.0, step=0.5,
                                               required=True),
            "w": st.column_config.NumberColumn("w (trọng số)", min_value=0.0, step=1.0),
        },
    )
    return edited_df


# -----------------------------------------------------------------------------
# 7. GIAO DIỆN: KẾT QUẢ
# -----------------------------------------------------------------------------
def results_section_ui():
    if not st.session_state.results:
        return

    # ---- Bảng 1: KPI CHUẨN -----
    st.subheader("📊 Tổng hợp các thông số")
    metrics_rows = [res["metrics"] for res in st.session_state.results.values()]
    standard_df = pd.DataFrame(metrics_rows).reindex(columns=backend.COMPARISON_COLUMNS)
    st.dataframe(
        standard_df.style.format({
            "Tổng thời gian hoàn thành": "{:.2f}",
            "Độ hữu dụng": "{:.2%}",
            "Số lượng công việc trung bình trong hệ thống": "{:.2f}",
            "Thời gian trung bình trong hệ thống": "{:.2f}",
        }),
        use_container_width=True, hide_index=True,
    )

    # ---- Đánh giá tự động dựa trên Bảng KPI chuẩn ---
    # Sắp xếp theo Tổng thời gian hoàn thành tăng dần (nhỏ nhất là tốt nhất)
    sorted_standard_df = standard_df.sort_values(by="Tổng thời gian hoàn thành", ascending=True).reset_index(drop=True)
    best_row = sorted_standard_df.iloc[0]

    st.success(f"🏆 **Luật điều độ tốt nhất: {best_row['Luật']}**")
   

    # ---- Chi tiết từng luật -------
    with st.expander("🔍 Xem chi tiết từng luật đã chạy"):
        tab_labels = list(st.session_state.results.keys())
        tabs = st.tabs([RULE_FULL_NAME[k] for k in tab_labels])
        for tab, rule_key in zip(tabs, tab_labels):
            with tab:
                res = st.session_state.results[rule_key]
                st.markdown(f"**Thứ tự điều độ:** {res['machine_order_text']}")
                display_df = res["result_df"].rename(columns=backend.DISPLAY_COLUMNS)
                st.dataframe(display_df.style.format(precision=2),
                             use_container_width=True, hide_index=True)
                if rule_key == "SRPT":
                    srpt_extra = {k: res["metrics"][k] for k in backend.SRPT_EXTRA_COLUMNS}
                    # 1. Khởi tạo df_srpt trước
                    df_srpt = pd.DataFrame([srpt_extra]).T.rename(columns={0: "Giá trị"})
                    
                    # 2. Gán tên index cho df_srpt (phải nằm trong khối if này)
                    df_srpt.index.name = "Thông số"
                    
                    # 3. Hiển thị bảng
                    st.dataframe(
                        df_srpt.style.format(precision=2),
                        use_container_width=False, 
                        hide_index=False
                    )

# -----------------------------------------------------------------------------
# 8. GIAO DIỆN: GANTT CHART
# -----------------------------------------------------------------------------
def gantt_section_ui():
    if not st.session_state.results:
        return
    st.subheader("📅 Biểu đồ Gantt & Tiến trình")
    
    rule_options = list(st.session_state.results.keys())
    selected_rule = st.selectbox(
        "Chọn Luật điều độ:",
        options=rule_options,
        format_func=lambda k: RULE_FULL_NAME.get(k, k),
        key="gantt_rule_select"
    )
    
    res = st.session_state.results[selected_rule]
    fig = plot_gantt_chart(res["schedule_result"], res["result_df"], selected_rule)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 📝 Diễn giải tiến trình gia công:")
    
    df_res = res["result_df"]
    for _, row in df_res.iterrows():
        job = row.get("job_id", "Công việc")
        start = row.get("start_time", 0)
        completion = row.get("completion_time", 0)
        tardiness = row.get("tardiness", 0)
        
        status_text = "✅ **Đúng hạn**" if tardiness == 0 else f"⚠️ **Trễ hạn** ({tardiness:.1f}h)"
        st.write(f"- **{job}**: Được gia công từ giờ thứ **{start:.1f}** đến giờ thứ **{completion:.1f}** — {status_text}")


# -----------------------------------------------------------------------------
# 9. main() - ĐIỀU PHỐI TOÀN BỘ LUỒNG CHẠY
# -----------------------------------------------------------------------------
def init_session_state():
    if "df" not in st.session_state:
        st.session_state.df = backend.validate_jobs(backend.SAMPLE_JOBS)
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0
    if "results" not in st.session_state:
        st.session_state.results = {}  # {rule_key: {schedule_result, result_df, metrics, extra_kpis, machine_order_text}}


def main():
    init_session_state()

    st.title("🏭 Điều độ máy đơn")

    selected_rules, run_clicked = sidebar_ui()
    current_df = input_section_ui()
    st.divider()

    if run_clicked:
        if not selected_rules:
            st.warning("⚠️ Vui lòng chọn ít nhất một luật điều độ ở thanh bên trước khi chạy.")
        else:
            try:
                validated_df = backend.validate_jobs(current_df)
            except ValueError as exc:
                st.error(f"❌ Dữ liệu không hợp lệ: {exc}")
                validated_df = None

            if validated_df is not None:
                st.session_state.df = validated_df
                results = {}
                with st.spinner("Đang tính toán lịch trình..."):
                    for rule_key in selected_rules:
                        scheduler_fn = SCHEDULERS[rule_key]
                        schedule_result = scheduler_fn(validated_df)
                        result_df = backend.calculate_job_results(validated_df, schedule_result)
                        metrics = backend.calculate_metrics(result_df, rule_key)
                        results[rule_key] = {
                            "schedule_result": schedule_result,
                            "result_df": result_df,
                            "metrics": metrics,
                            "machine_order_text": backend.format_machine_order(schedule_result),
                        }
                st.session_state.results = results
                st.success(f"✅ Đã chạy xong {len(selected_rules)} luật cho {len(validated_df)} công việc.")

    results_section_ui()
    st.divider()
    gantt_section_ui()

    if not st.session_state.results:
        st.info(
            "👈 Kiểm tra/sửa dữ liệu công việc, chọn ít nhất một luật điều độ ở thanh bên, "
            "sau đó nhấn **'🚀 Điều độ'** để xem kết quả."
        )


if __name__ == "__main__":
    main()
