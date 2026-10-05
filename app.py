# -*- coding: utf-8 -*-

import html
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import dieu_do_may_don as backend

st.set_page_config(page_title="Điều độ máy đơn", layout="wide", initial_sidebar_state="collapsed")

# Thêm luật mới: viết schedule_xxx() trong dieu_do_may_don.py rồi thêm 1 dòng vào hai dict dưới.
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
RULE_DESC = {
    "FCFS": "Ưu tiên công việc đến trước",
    "SPT": "Ưu tiên công việc có thời gian gia công ngắn nhất",
    "EDD": "Ưu tiên công việc có thời hạn hoàn thành sớm nhất",
    "LPT": "Ưu tiên công việc có thời gian gia công dài nhất",
    "SRPT": "Ưu tiên công việc có thời gian gia công còn lại ngắn nhất (cho phép ngắt)",
}
MACHINE_LABEL = "Máy đơn"
SOURCE_MANUAL, SOURCE_FILE = "Nhập thủ công", "Tải file CSV/Excel"

_VERSION = tuple(int(x) for x in st.__version__.split(".")[:2] if x.isdigit())
STRETCH = {"width": "stretch"} if _VERSION >= (1, 49) else {"use_container_width": True}

# Bảng màu cho biểu đồ Gantt.
APPLE_COLORS = [
    "#0A84FF", "#30D158", "#FF9F0A", "#BF5AF2", "#FF453A", "#64D2FF",
    "#FFD60A", "#5E5CE6", "#AC8E68", "#63E6E2", "#FF375F", "#98989D",
]
FONT_STACK = '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif'


# -----------------------------------------------------------------------------
# 1. PHONG CÁCH GIAO DIỆN
# Quy tắc màu: chữ đen trên nền trắng; chữ trắng trên nền đen; nhấn mạnh bằng chữ đỏ.
# -----------------------------------------------------------------------------
STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{--pad:0px;--bg:#f5f5f7;--card:#fff;--ink:#000;--mute:#1d1d1f;--line:#d2d2d7;--soft:#ececf0;
      --red:#d70015;--red-on-dark:#ff453a;}

/* Nền tảng và chữ: ép chữ đen trên nền sáng */
.stApp{background:var(--bg);color:var(--ink);}
.stApp,.stApp p,.stApp label,.stApp li,.stApp button,.stApp input,.stApp textarea,.stApp table,
.stApp h1,.stApp h2,.stApp h3,.stApp div[data-testid="stMarkdownContainer"]{
  color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Inter","Helvetica Neue",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;letter-spacing:-.011em;}
header[data-testid="stHeader"],footer,#MainMenu,[data-testid="stToolbar"],[data-testid="stDecoration"],
[data-testid="stSidebar"],[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"]{display:none!important;}
.block-container{max-width:1080px;padding:96px 24px 140px!important;}
/* Tăng khoảng cách giữa các hàng/khối */
[data-testid="stVerticalBlock"]{gap:2rem;}

/* Giữ nguyên font biểu tượng của Streamlit (sửa lỗi chữ arrow_down chồng lên tiêu đề expander) */
.stApp [data-testid="stIconMaterial"],.stApp span[class*="material"]{
  font-family:"Material Symbols Rounded","Material Symbols Outlined"!important;letter-spacing:normal!important;}
.stApp span{color:#000;}

/* Thanh điều hướng: trái = tên môn, phải = nhóm */
.nav{position:fixed;top:0;left:0;right:0;height:52px;z-index:1000;background:rgba(255,255,255,.92);
  -webkit-backdrop-filter:saturate(180%) blur(20px);backdrop-filter:saturate(180%) blur(20px);
  border-bottom:1px solid rgba(0,0,0,.12);}
.nav>div{box-sizing:border-box;max-width:1080px;height:100%;margin:0 auto;display:flex;align-items:center;
  justify-content:space-between;padding:0 calc(24px + var(--pad));font-size:15px;}
.nav b{font-weight:600;color:#000;}
.nav span{color:#000;font-size:14px;font-weight:500;}

/* Hero: mô tả bên trái, tiêu đề bên phải, cùng một hàng */
.hero{display:flex;align-items:baseline;justify-content:space-between;gap:24px;flex-wrap:wrap;
  padding:48px var(--pad) 28px;}
.hero .t{font-size:clamp(36px,5.4vw,60px);line-height:1.05;font-weight:600;letter-spacing:-.03em;color:#000;text-align:left;}
.hero .s{font-size:clamp(17px,2.1vw,24px);line-height:1.3;color:#000;font-weight:500;text-align:right;}

/* Thẻ nội dung */
.card-anchor,div[data-testid="stElementContainer"]:has(.card-anchor),.element-container:has(.card-anchor){display:none!important;}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-anchor):not(:has(div[data-testid="stVerticalBlockBorderWrapper"] .card-anchor)){
  background:var(--card)!important;border:none!important;border-radius:28px!important;padding:44px 40px 40px!important;
  box-shadow:none!important;margin-bottom:1.5rem;}
.eyebrow{font-size:14px;font-weight:600;color:#000;letter-spacing:.01em;margin-bottom:8px;}
.sec-title{font-size:clamp(28px,3.6vw,40px);line-height:1.1;font-weight:600;letter-spacing:-.025em;color:#000;}
.sec-sub{font-size:17px;line-height:1.5;color:#000;margin:14px 0 8px;max-width:640px;}
.hint{font-size:14px;line-height:1.6;color:#000;margin:8px 0;}
.hint b{color:#000;font-weight:600;}
.mini{font-size:15px;font-weight:600;color:#000;margin:14px 0 6px;}

/* Nút mặc định: nền xám nhạt, chữ đen */
.stApp .stButton>button{border-radius:980px;border:none;box-shadow:none;background:#e8e8ed;color:#000;
  padding:10px 22px;min-height:44px;font-size:17px;font-weight:400;transition:background .2s ease;}
.stApp .stButton>button:hover{background:#dcdce1;color:#000;}
.stApp .stButton>button p{color:inherit;font-size:17px;}
/* Nút chính: nền đen, chữ trắng */
.stApp .stButton>button[kind="primary"],.stApp .stButton>button[data-testid="stBaseButton-primary"]{
  background:#000;color:#fff;min-height:52px;font-size:19px;margin-top:12px;}
.stApp .stButton>button[kind="primary"] p,.stApp .stButton>button[data-testid="stBaseButton-primary"] p{color:#fff!important;}
.stApp .stButton>button[kind="primary"]:hover,.stApp .stButton>button[data-testid="stBaseButton-primary"]:hover{background:#2a2a2a;color:#fff;}

/* Radio thành bộ chọn phân đoạn */
.stApp div[role="radiogroup"]{background:#e8e8ed;border-radius:980px;padding:3px;display:inline-flex;gap:0;flex-wrap:nowrap;}
.stApp div[role="radiogroup"] label{margin:0!important;padding:7px 20px;border-radius:980px;cursor:pointer;}
.stApp div[role="radiogroup"] label>div:not(:has(p)){display:none!important;}
.stApp div[role="radiogroup"] label p{font-size:15px;font-weight:500;white-space:nowrap;color:#000;}
.stApp div[role="radiogroup"] label:has(input:checked){background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.14);}

/* Ô chọn luật */
div[data-testid="stColumn"]:has(div[data-testid="stCheckbox"]),div[data-testid="column"]:has(div[data-testid="stCheckbox"]){
  background:var(--bg);border-radius:20px;padding:20px 18px 16px;}
.stApp div[data-testid="stCheckbox"] label p{font-size:19px;font-weight:600;letter-spacing:-.02em;color:#000;}
.rule-note{font-size:13px;line-height:1.4;color:#000;margin:2px 0 0 30px;}

/* Bảng nhập liệu, tải file, chọn */
div[data-testid="stDataFrame"],div[data-testid="stDataEditor"]{border-radius:16px;overflow:hidden;border:1px solid var(--line);}
section[data-testid="stFileUploaderDropzone"],div[data-testid="stFileUploaderDropzone"]{background:var(--bg);border:1px dashed var(--line);border-radius:18px;}
.stApp div[data-baseweb="select"]>div{border-radius:12px;background:#fff!important;border:1px solid var(--line);min-height:44px;color:#000!important;}
.stApp div[data-baseweb="select"] *{color:#000!important;}
div[data-baseweb="popover"] *{color:#000!important;background-color:#fff;}
div[data-baseweb="popover"] li:hover{background-color:#f0f0f3!important;}
.stApp [data-testid="stCaptionContainer"],.stApp .stCaption{color:#000;}

/* Thanh công cụ của bảng nhập liệu (biểu tượng thùng rác) luôn hiển thị */
[data-testid="stElementToolbar"]{opacity:1!important;visibility:visible!important;}

/* Thông báo: chữ đen trên nền sáng; lỗi/cảnh báo dùng chữ đỏ để nhấn mạnh */
.note{padding:16px 20px;border-radius:14px;font-size:15px;line-height:1.5;margin:8px 0;color:#000;}
.note.ok{background:#e6f6ea;color:#000;}
.note.info{background:#e8f1fc;color:#000;}
.note.err{background:#fdecea;color:var(--red);font-weight:600;}
.note.warn{background:#fff3df;color:var(--red);font-weight:600;}

/* Bảng kết quả */
.tbl-wrap{overflow-x:auto;margin:10px 0 6px;}
.stApp table.tbl{width:100%;border-collapse:collapse;border:none;font-size:15px;font-variant-numeric:tabular-nums;}
.stApp table.tbl th{font-size:13px;font-weight:600;color:#000;text-align:left;padding:14px 16px;
  border:none;border-bottom:1px solid var(--line);vertical-align:bottom;background:transparent;}
.stApp table.tbl td{padding:18px 16px;border:none;border-bottom:1px solid var(--soft);color:#000;background:transparent;}
.stApp table.tbl tr:last-child td{border-bottom:none;}
.stApp table.tbl .num{text-align:right;}
/* Dòng nổi bật: chữ đỏ */
.stApp table.tbl tr.hl td{font-weight:600;color:var(--red);}
.stApp table.dense td,.stApp table.dense th{padding:14px 12px;font-size:14px;}

/* Luật tốt nhất: nền đen, chữ trắng, giá trị nhấn mạnh bằng chữ đỏ */
.best{background:#000;border-radius:22px;padding:32px 36px;margin-top:20px;}
.best .l{font-size:14px;font-weight:600;color:#fff;}
.best .v{font-size:clamp(40px,6vw,64px);line-height:1.05;font-weight:600;letter-spacing:-.03em;margin:10px 0 8px;color:var(--red-on-dark);}
.best .s{font-size:16px;color:#fff;}

/* Tab, expander */
.stApp button[data-baseweb="tab"]{font-size:16px;padding:10px 4px;margin-right:18px;color:#000;}
.stApp button[data-baseweb="tab"] p{color:#000;}
.stApp button[data-baseweb="tab"][aria-selected="true"]{color:#000;font-weight:600;}
.stApp div[data-baseweb="tab-highlight"]{background:var(--red)!important;}
.stApp div[data-testid="stExpander"] details{border:1px solid var(--line);border-radius:18px;background:#fff;}
.stApp div[data-testid="stExpander"] summary p{font-size:17px;font-weight:500;color:#000;}
.order{font-size:15px;line-height:1.7;color:#000;margin:8px 0 14px;}
.order b{font-weight:600;}

/* Diễn giải tiến trình */
sub{font-size:.75em;line-height:0;}
ul.steps{list-style:none;margin:10px 0 0;padding:0;}
ul.steps li{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:20px 0;border-bottom:1px solid var(--soft);}
ul.steps li:last-child{border-bottom:none;}
ul.steps b{font-size:17px;font-weight:600;display:block;color:#000;margin-bottom:4px;}
ul.steps em{font-style:normal;font-size:15px;color:#000;}
.pill{display:inline-block;padding:6px 14px;border-radius:980px;font-size:13px;font-weight:500;white-space:nowrap;}
.pill.ok{background:#e6f6ea;color:#000;}
.pill.late{background:#fdecea;color:var(--red);font-weight:600;}

@media (max-width:640px){
  div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-anchor):not(:has(div[data-testid="stVerticalBlockBorderWrapper"] .card-anchor)){padding:28px 20px 26px!important;}
  .stApp div[role="radiogroup"]{display:flex;}
  .stApp div[role="radiogroup"] label{padding:7px 12px;}
  .hero{flex-direction:column;align-items:flex-start;}
  .hero .s{text-align:left;}
}
</style>
"""


def esc(value) -> str:
    return html.escape(str(value))


def note(kind: str, text: str):
    """Thông báo dạng thẻ mềm. kind: ok | err | warn | info."""
    st.markdown(f'<div class="note {kind}">{esc(text)}</div>', unsafe_allow_html=True)


def card_start():
    """Đánh dấu container hiện tại là một thẻ trắng bo góc (xem CSS)."""
    st.markdown('<span class="card-anchor"></span>', unsafe_allow_html=True)


def section_head(eyebrow: str, title: str, sub: str = ""):
    eyebrow_html = f'<div class="eyebrow">{esc(eyebrow)}</div>' if eyebrow else ""
    sub_html = f'<p class="sec-sub">{esc(sub)}</p>' if sub else ""
    st.markdown(
        f'{eyebrow_html}<div class="sec-title">{esc(title)}</div>{sub_html}',
        unsafe_allow_html=True,
    )


def html_table(df: pd.DataFrame, formats: dict | None = None, highlight=None, dense: bool = False):
    """Vẽ bảng chỉ đọc bằng HTML để đồng bộ phong cách; cột số căn phải."""
    formats = formats or {}
    numeric = [i > 0 and pd.api.types.is_numeric_dtype(df[c]) for i, c in enumerate(df.columns)]
    def sub(text: str) -> str:
        # Đổi chỉ số dưới dạng gạch dưới (F_j, C_j...) thành chỉ số dưới thật.
        return re.sub(r"(?<=[A-Za-z])_([A-Za-z0-9]+)", r"<sub>\1</sub>", esc(text))

    head = "".join(
        f'<th class="{"num" if num else ""}">{sub(c)}</th>' for c, num in zip(df.columns, numeric)
    )
    body = []
    for rec in df.to_dict("records"):
        cells = []
        for (col, value), num in zip(rec.items(), numeric):
            if col in formats:
                text = formats[col].format(value)
            elif isinstance(value, (float, np.floating)):
                text = f"{value:.2f}"
            else:
                text = str(value)
            cells.append(f'<td class="{"num" if num else ""}">{esc(text)}</td>')
        row_cls = ' class="hl"' if highlight is not None and rec[df.columns[0]] == highlight else ""
        body.append(f"<tr{row_cls}>{''.join(cells)}</tr>")
    table_cls = "tbl dense" if dense else "tbl"
    st.markdown(
        f'<div class="tbl-wrap"><table class="{table_cls}"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# 2. ĐỌC FILE NGƯỜI DÙNG TẢI LÊN
# -----------------------------------------------------------------------------
def read_uploaded_jobs(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        raw_df = pd.read_csv(uploaded_file, dtype={"job_id": str}, keep_default_na=False)
    elif name.endswith((".xlsx", ".xls")):
        raw_df = pd.read_excel(uploaded_file, sheet_name=0, dtype={"job_id": str}, keep_default_na=False)
    else:
        raise ValueError("Chỉ hỗ trợ file CSV (.csv) hoặc Excel (.xlsx).")
    return backend.validate_jobs(raw_df)


# -----------------------------------------------------------------------------
# 3. BIỂU ĐỒ GANTT
# -----------------------------------------------------------------------------
def plot_gantt_chart(schedule_result: dict, result_df: pd.DataFrame, rule_key: str):
    seg_df = pd.DataFrame([
        {"Job": seg["job_id"], "Start": float(seg["start"]), "End": float(seg["end"]),
         "Duration": float(seg["end"]) - float(seg["start"])}
        for seg in schedule_result["segments"]
    ])
    seg_df = seg_df.merge(
        result_df[["job_id", "p", "r", "d", "tardiness", "completion_time"]],
        left_on="Job", right_on="job_id", how="left",
    )
    seg_df["Machine"] = MACHINE_LABEL
    seg_df["Trạng thái"] = np.where(seg_df["tardiness"] > 0, "Trễ hạn", "Đúng hạn")

    fig = px.bar(
        seg_df, x="Duration", y="Machine", base="Start", color="Job",
        pattern_shape="Trạng thái", pattern_shape_map={"Trễ hạn": "/", "Đúng hạn": ""},
        orientation="h", color_discrete_sequence=APPLE_COLORS,
        hover_data={"Job": True, "Start": ":.2f", "End": ":.2f", "Duration": False, "Machine": False,
                    "p": ":.2f", "r": ":.2f", "d": ":.2f", "tardiness": ":.2f"},
    )
    fig.update_traces(marker_line_color="#ffffff", marker_line_width=3)
    time_points = sorted(set(seg_df["Start"].round(6)) | set(seg_df["End"].round(6)))
    fig.update_xaxes(title="", tickmode="array", tickvals=time_points,
                     ticktext=[f"{t:g}" for t in time_points], gridcolor="#ececf0", zeroline=False,
                     linecolor="#d2d2d7", rangemode="tozero")
    fig.update_yaxes(title="", showticklabels=False, showgrid=False)
    fig.update_layout(
        height=240, bargap=0.25, legend_title_text="",
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0),
        font=dict(family=FONT_STACK, size=14, color="#000000"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff",
        margin=dict(l=8, r=8, t=48, b=8),
        hoverlabel=dict(bgcolor="#ffffff", font=dict(family=FONT_STACK, color="#000000")),
    )
    return fig


# -----------------------------------------------------------------------------
# 4. GIAO DIỆN: ĐẦU TRANG
# -----------------------------------------------------------------------------
def header_ui():
    st.markdown(
        '<div class="nav"><div><b>Điều độ trong chuỗi cung ứng</b><span>L02 - Nhóm 4</span></div></div>'
        '<div class="hero"><div class="t">Điều độ máy đơn</div>'
        '<div class="s">Các giải thuật điều độ kinh nghiệm</div></div>',
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# 5. GIAO DIỆN: DỮ LIỆU CÔNG VIỆC (nguồn dữ liệu + bảng nhập liệu)
# -----------------------------------------------------------------------------
def data_section_ui() -> pd.DataFrame:
    with st.container(border=True):
        card_start()
        section_head("", "Dữ liệu công việc.", "Chọn nguồn dữ liệu, sau đó kiểm tra hoặc chỉnh sửa trực tiếp trong bảng.")

        col_source, col_reset = st.columns([4, 1])
        with col_source:
            input_method = st.radio("Nguồn dữ liệu công việc", [SOURCE_MANUAL, SOURCE_FILE],
                                    horizontal=True, label_visibility="collapsed")
        with col_reset:
            if st.button("Reset", **STRETCH):
                st.session_state.df = backend.validate_jobs(backend.SAMPLE_JOBS)
                st.session_state.editor_version += 1
                st.session_state.last_uploaded_sig = None
                st.session_state.results = {}
                st.rerun()

        if input_method == SOURCE_FILE:
            uploaded_file = st.file_uploader("Chọn file (.csv, .xlsx)", type=["csv", "xlsx", "xls"])
            if uploaded_file is not None:
                sig = f"{uploaded_file.name}-{uploaded_file.size}"
                if sig != st.session_state.get("last_uploaded_sig"):
                    try:
                        validated_df = read_uploaded_jobs(uploaded_file)
                        st.session_state.df = validated_df
                        st.session_state.editor_version += 1
                        st.session_state.last_uploaded_sig = sig
                        note("ok", f"Đã tải {len(validated_df)} công việc hợp lệ.")
                    except ValueError as exc:
                        note("err", f"File không hợp lệ: {exc}")
                    except Exception as exc:
                        note("err", f"Lỗi khi đọc file: {exc}")
            st.markdown(
                '<div class="hint"><b>Cột bắt buộc:</b> job_id, p, r, d. '
                '<b>Cột tùy chọn:</b> w (trọng số, mặc định 1 nếu để trống). '
                'Điều kiện: p &gt; 0; r, d, w ≥ 0; job_id không được trùng.</div>',
                unsafe_allow_html=True,
            )

        st.caption("Nhấn Thêm dòng để thêm công việc mới. Để xóa, tích ô Chọn ở đầu dòng rồi nhấn biểu tượng thùng rác.")

        # Cột "Chọn" chỉ dùng để đánh dấu dòng cần xóa, không đi vào dữ liệu điều độ.
        display_df = st.session_state.df.reset_index(drop=True).copy()
        display_df.insert(0, "Chọn", False)
        edited = st.data_editor(
            display_df,
            num_rows="fixed",
            hide_index=True,
            key=f"data_editor_{st.session_state.editor_version}",
            column_config={
                "Chọn": st.column_config.CheckboxColumn("Chọn", width="small"),
                "job_id": st.column_config.TextColumn("J (công việc)", required=True),
                "p": st.column_config.NumberColumn("p (thời gian gia công)", min_value=0.01, step=0.5, required=True),
                "r": st.column_config.NumberColumn("r (thời gian đến)", min_value=0.0, step=0.5, required=True),
                "d": st.column_config.NumberColumn("d (thời gian tới hạn)", min_value=0.0, step=0.5, required=True),
                "w": st.column_config.NumberColumn("w (trọng số)", min_value=0.0, step=1.0),
            },
            **STRETCH,
        )
        current_df = edited.drop(columns="Chọn").reset_index(drop=True)

        icon_kw = {"icon": ":material/delete:"} if _VERSION >= (1, 40) else {}
        col_add, col_del, _ = st.columns([1.3, 2.2, 4])
        with col_add:
            add_clicked = st.button("Thêm dòng", key="add_row", **STRETCH)
        with col_del:
            del_clicked = st.button("Xóa dòng đã chọn", key="delete_rows", **icon_kw, **STRETCH)

        if add_clicked:
            used = {str(j) for j in current_df["job_id"].dropna()}
            n = len(current_df) + 1
            while f"J{n}" in used:
                n += 1
            defaults = {"job_id": f"J{n}", "p": 1.0, "r": 0.0, "d": 1.0, "w": 1.0}
            new_row = {c: defaults.get(c) for c in current_df.columns}
            st.session_state.df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)
            st.session_state.editor_version += 1
            st.session_state.results = {}
            st.rerun()
        if del_clicked:
            keep = ~edited["Chọn"].fillna(False).astype(bool).to_numpy()
            if keep.all():
                note("warn", "Chưa chọn dòng nào để xóa.")
            else:
                st.session_state.df = current_df[keep].reset_index(drop=True)
                st.session_state.editor_version += 1
                st.session_state.results = {}
                st.rerun()
        return current_df


# -----------------------------------------------------------------------------
# 6. GIAO DIỆN: CHỌN LUẬT VÀ CHẠY
# -----------------------------------------------------------------------------
def rules_section_ui():
    st.session_state.setdefault("rules_version", 0)
    st.session_state.setdefault("rules_default", True)

    with st.container(border=True):
        card_start()
        section_head("", "Luật điều độ.", "Tích chọn một hoặc nhiều luật trong bảng để so sánh.")

        col_all, col_none, _ = st.columns([1.3, 1.3, 4])
        with col_all:
            if st.button("Chọn tất cả", key="rules_all", **STRETCH):
                st.session_state.rules_default = True
                st.session_state.rules_version += 1
                st.rerun()
        with col_none:
            if st.button("Bỏ chọn tất cả", key="rules_none", **STRETCH):
                st.session_state.rules_default = False
                st.session_state.rules_version += 1
                st.rerun()

        rules_df = pd.DataFrame({
            "Chọn": [st.session_state.rules_default] * len(SCHEDULERS),
            "Luật": list(SCHEDULERS.keys()),
            "Tên đầy đủ": [RULE_FULL_NAME[k].split(" - ", 1)[-1] for k in SCHEDULERS],
            "Nguyên tắc ưu tiên": [RULE_DESC.get(k, "") for k in SCHEDULERS],
        })
        edited_rules = st.data_editor(
            rules_df,
            hide_index=True,
            num_rows="fixed",
            key=f"rules_editor_{st.session_state.rules_version}",
            disabled=["Luật", "Tên đầy đủ", "Nguyên tắc ưu tiên"],
            column_config={
                "Chọn": st.column_config.CheckboxColumn("Chọn", width="small"),
                "Luật": st.column_config.TextColumn("Luật", width="small"),
                "Tên đầy đủ": st.column_config.TextColumn("Tên đầy đủ", width="medium"),
                "Nguyên tắc ưu tiên": st.column_config.TextColumn("Nguyên tắc ưu tiên", width="large"),
            },
            **STRETCH,
        )
        selected_rules = edited_rules.loc[edited_rules["Chọn"], "Luật"].tolist()

        run_clicked = st.button("Điều độ", type="primary", **STRETCH)
    return selected_rules, run_clicked


# -----------------------------------------------------------------------------
# 7. GIAO DIỆN: KẾT QUẢ
# -----------------------------------------------------------------------------
def results_section_ui():
    if not st.session_state.results:
        return
    standard_df = pd.DataFrame(
        [res["metrics"] for res in st.session_state.results.values()]
    ).reindex(columns=backend.COMPARISON_COLUMNS)
    best_row = standard_df.sort_values("Tổng thời gian hoàn thành", kind="stable").iloc[0]

    with st.container(border=True):
        card_start()
        section_head("Kết quả", "Tổng hợp các thông số.")
        html_table(standard_df, formats={
            "Tổng thời gian hoàn thành": "{:.2f}",
            "Độ hữu dụng": "{:.2%}",
            "Số lượng công việc trung bình trong hệ thống": "{:.2f}",
            "Thời gian trung bình trong hệ thống": "{:.2f}",
        }, highlight=best_row["Luật"])

        st.markdown(
            f'<div class="best"><div class="l">Luật điều độ tốt nhất</div>'
            f'<div class="v">{esc(best_row["Luật"])}</div>'
            f'<div class="s">Tổng thời gian hoàn thành nhỏ nhất: {best_row["Tổng thời gian hoàn thành"]:.2f}</div></div>',
            unsafe_allow_html=True,
        )

        with st.expander("Xem chi tiết từng luật đã chạy"):
            rule_keys = list(st.session_state.results.keys())
            for tab, rule_key in zip(st.tabs(rule_keys), rule_keys):
                with tab:
                    res = st.session_state.results[rule_key]
                    st.markdown(f'<div class="mini">{esc(RULE_FULL_NAME[rule_key])}</div>'
                                f'<div class="order"><b>Thứ tự điều độ:</b> {esc(res["machine_order_text"])}</div>',
                                unsafe_allow_html=True)
                    html_table(res["result_df"].rename(columns=backend.DISPLAY_COLUMNS), dense=True)
                    if rule_key == "SRPT":
                        st.markdown('<div class="mini">Bảng thời gian chi tiết của từng công việc (SRPT)</div>',
                                    unsafe_allow_html=True)
                        html_table(backend.calculate_srpt_job_times(res["result_df"]), dense=True)


# -----------------------------------------------------------------------------
# 8. GIAO DIỆN: GANTT
# -----------------------------------------------------------------------------
def gantt_section_ui():
    if not st.session_state.results:
        return
    with st.container(border=True):
        card_start()
        section_head("Tiến trình", "Biểu đồ Gantt.")
        selected_rule = st.selectbox(
            "Chọn luật điều độ",
            options=list(st.session_state.results.keys()),
            format_func=lambda k: RULE_FULL_NAME.get(k, k),
            key="gantt_rule_select",
        )
        res = st.session_state.results[selected_rule]
        st.plotly_chart(plot_gantt_chart(res["schedule_result"], res["result_df"], selected_rule),
                        theme=None, config={"displayModeBar": False}, **STRETCH)

        st.markdown('<div class="mini">Diễn giải tiến trình gia công</div>', unsafe_allow_html=True)
        items = []
        for row in res["result_df"].to_dict("records"):
            late = row["tardiness"] > 0
            pill = (f'<span class="pill late">Trễ hạn ({row["tardiness"]:.1f}h)</span>' if late
                    else '<span class="pill ok">Đúng hạn</span>')
            items.append(
                f'<li><div><b>{esc(row["job_id"])}</b>'
                f'<em>Gia công từ giờ thứ {row["start_time"]:.1f} đến giờ thứ {row["completion_time"]:.1f}</em></div>'
                f'{pill}</li>'
            )
        st.markdown(f'<ul class="steps">{"".join(items)}</ul>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 9. main() - ĐIỀU PHỐI LUỒNG CHẠY
# -----------------------------------------------------------------------------
def init_session_state():
    if "df" not in st.session_state:
        st.session_state.df = backend.validate_jobs(backend.SAMPLE_JOBS)
    if "editor_version" not in st.session_state:
        st.session_state.editor_version = 0
    if "results" not in st.session_state:
        st.session_state.results = {}  # {rule_key: {schedule_result, result_df, metrics, machine_order_text}}


def run_schedulers(validated_df: pd.DataFrame, selected_rules: list) -> dict:
    results = {}
    for rule_key in selected_rules:
        schedule_result = SCHEDULERS[rule_key](validated_df)
        result_df = backend.calculate_job_results(validated_df, schedule_result)
        results[rule_key] = {
            "schedule_result": schedule_result,
            "result_df": result_df,
            "metrics": backend.calculate_metrics(result_df, rule_key),
            "machine_order_text": backend.format_machine_order(schedule_result),
        }
    return results


def main():
    init_session_state()
    st.markdown(STYLE, unsafe_allow_html=True)
    header_ui()

    current_df = data_section_ui()
    selected_rules, run_clicked = rules_section_ui()

    if run_clicked:
        if not selected_rules:
            note("warn", "Vui lòng chọn ít nhất một luật điều độ trước khi chạy.")
        else:
            try:
                validated_df = backend.validate_jobs(current_df)
            except ValueError as exc:
                note("err", f"Dữ liệu không hợp lệ: {exc}")
            else:
                st.session_state.df = validated_df
                with st.spinner("Đang tính toán lịch trình..."):
                    st.session_state.results = run_schedulers(validated_df, selected_rules)
                note("ok", f"Đã chạy xong {len(selected_rules)} luật cho {len(validated_df)} công việc.")

    results_section_ui()
    gantt_section_ui()

    if not st.session_state.results:
        note("info", "Kiểm tra hoặc sửa dữ liệu công việc, chọn ít nhất một luật điều độ, "
                     "sau đó nhấn Điều độ để xem kết quả.")


if __name__ == "__main__":
    main()
