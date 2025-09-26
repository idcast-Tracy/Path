# 打开网页，在cmd命令界面运行下面一段
# streamlit run C:\Users\30821\Desktop\Shiny复健\04网页计算器\04py部署\Path.py [ARGUMENTS]


import openslide
import streamlit as st
from PIL import Image
import io
import base64
import tempfile
import os

# 设置页面配置
st.set_page_config(
    page_title="病理切片分析平台",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 28px;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 30px;
    }
    .score-box {
        background-color: #e7f3ff;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin-bottom: 30px;
    }
    .info-box {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #ffc107;
    }
    .success-box {
        background-color: #d4edda;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)


def analyze_wsi(wsi_path):
    """分析WSI文件的函数"""
    try:
        # 打开WSI文件
        slide = openslide.OpenSlide(wsi_path)

        # 基本信息获取
        format_info = str(slide.detect_format(wsi_path)) if slide.detect_format(wsi_path) else "Unknown"
        level_count = int(slide.level_count)
        dimensions_level0 = str(slide.level_dimensions[0])
        downsamples = [float(x) for x in slide.level_downsamples]

        mpp_x = slide.properties.get("openslide.mpp-x", "N/A")
        mpp_y = slide.properties.get("openslide.mpp-y", "N/A")
        vendor = slide.properties.get("openslide.vendor", "Unknown")

        # 生成缩略图
        thumbnail_level = min(2, slide.level_count - 1)
        thumb_size = slide.level_dimensions[thumbnail_level]

        thumbnail = slide.read_region(
            location=(0, 0),
            level=thumbnail_level,
            size=thumb_size
        ).convert("RGB")

        max_size = (512, 512)
        thumbnail.thumbnail(max_size)

        slide.close()

        return {
            "success": True,
            "format": format_info,
            "level_count": level_count,
            "dimensions_level0": dimensions_level0,
            "downsamples": downsamples,
            "mpp_x": mpp_x,
            "mpp_y": mpp_y,
            "vendor": vendor,
            "thumbnail": thumbnail
        }

    except Exception as e:
        return {"success": False, "error": f"错误: {str(e)}"}


def calculate_plnm_score(lvi, tumor_budding, pdcs_level, histologic_grade2, sm2):
    """计算PLNM分数"""
    score = lvi * 4 + tumor_budding * 3 + pdcs_level * 2 + histologic_grade2 * 3 + sm2 * 1
    return score


def main():
    # 页面标题
    st.markdown('<div class="main-header">病理切片分析平台</div>', unsafe_allow_html=True)

    # 侧边栏 - 用户输入
    with st.sidebar:
        st.header("病理参数设置")

        # 使用columns创建更紧凑的布局
        col1, col2 = st.columns(2)

        with col1:
            lvi = st.radio("LVI:", options=[0, 1], format_func=lambda x: "Negative" if x == 0 else "Positive")
            tumor_budding = st.radio("Tumor budding:", options=[0, 1],
                                     format_func=lambda x: "Negative" if x == 0 else "Positive")
            pdcs_level = st.radio("PDCs level:", options=[0, 1],
                                  format_func=lambda x: "Negative" if x == 0 else "Positive")

        with col2:
            histologic_grade2 = st.radio("Histologic grade2:", options=[0, 1],
                                         format_func=lambda x: "Negative" if x == 0 else "Positive")
            sm2 = st.radio("SM2:", options=[0, 1], format_func=lambda x: "Negative" if x == 0 else "Positive")

        st.markdown("---")

        # 文件上传
        st.header("WSI文件上传")
        uploaded_file = st.file_uploader(
            "上传全切片图像(WSI):",
            type=['svs', 'tif', 'tiff', 'ndpi', 'scn', 'mrxs', 'vms', 'vmu'],
            help="支持 .svs, .tif, .tiff, .ndpi, .scn, .mrxs, .vms, .vmu 格式"
        )

    # 主内容区域
    # PLNM Score计算结果显示
    plnm_score = calculate_plnm_score(lvi, tumor_budding, pdcs_level, histologic_grade2, sm2)

    st.markdown(f"""
    <div class="score-box">
        <h3>PLNM Score Calculation = LVI × 4 + Tumor budding × 3 + PDCs level × 2 + Histologic grade2 × 3 + SM2 × 1</h3>
        <h2 style="text-align: center; color: #1f77b4;">PLNM Score = {plnm_score}</h2>
    </div>
    """, unsafe_allow_html=True)

    # WSI文件分析结果显示
    if uploaded_file is not None:
        # 创建两列布局
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("WSI文件基本信息")

            # 保存上传的文件到临时位置
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            # 显示分析进度
            with st.spinner("正在分析WSI文件..."):
                analysis_result = analyze_wsi(tmp_path)

            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except:
                pass

            if analysis_result["success"]:
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.write("**WSI文件分析结果:**")
                st.write("=================")
                st.write(f"**文件格式:** {analysis_result['format']}")
                st.write(f"**层级数:** {analysis_result['level_count']}")
                st.write(f"**基准层尺寸:** {analysis_result['dimensions_level0']} (宽×高)")

                if analysis_result['downsamples']:
                    downsamples_str = ", ".join([f"{x:.2f}" for x in analysis_result['downsamples']])
                    st.write(f"**层级降采样系数:** {downsamples_str}")
                else:
                    st.write("**层级降采样系数:** 无法获取")

                st.write(
                    f"**扫描分辨率:** {analysis_result['mpp_x']} μm/pixel(x), {analysis_result['mpp_y']} μm/pixel(y)")
                st.write(f"**厂商信息:** {analysis_result['vendor']}")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.error(f"分析失败: {analysis_result['error']}")

        with col2:
            st.subheader("WSI缩略图")
            if analysis_result["success"] and "thumbnail" in analysis_result:
                # 显示缩略图
                thumbnail = analysis_result["thumbnail"]
                st.image(thumbnail, caption="WSI缩略图", use_container_width=True)

                # 显示图像信息
                st.write(f"**缩略图尺寸:** {thumbnail.size[0]} × {thumbnail.size[1]} 像素")
            else:
                st.warning("无可用图像")
                # 显示占位图
                st.image(Image.new('RGB', (400, 400), color='gray'),
                         caption="无图像", use_container_width=True)

    else:
        # 没有上传文件时的提示
        st.info("请在左侧上传WSI文件以进行分析")

        # 创建两列占位
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("WSI文件基本信息")
            st.markdown('<div class="info-box">请上传WSI文件以查看分析结果</div>', unsafe_allow_html=True)

        with col2:
            st.subheader("WSI缩略图")
            st.image(Image.new('RGB', (400, 400), color='lightgray'),
                     caption="等待上传文件", use_container_width=True)


if __name__ == "__main__":
    # 检查openslide是否可用
    try:
        import openslide

        main()
    except ImportError:
        st.error("""
        **错误: openslide-python 库未安装**

        请使用以下命令安装所需依赖：
        ```bash
        pip install openslide-python streamlit Pillow
        ```

        另外，您还需要安装系统级的OpenSlide库：
        - **Windows**: 下载OpenSlide Win64并设置环境变量
        - **Linux**: `sudo apt-get install openslide-tools`
        - **macOS**: `brew install openslide`
        """)
