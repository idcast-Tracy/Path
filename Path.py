# 打开网页，在cmd命令界面运行下面一段
# streamlit run C:\Users\30821\Desktop\Pathlogical\Path.py [ARGUMENTS]

import openslide
import streamlit as st
from PIL import Image
import io
import base64
import tempfile
import os
import time
from datetime import datetime
import json

# 设置页面配置
st.set_page_config(
    page_title="病理切片分析平台",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 设置最大上传大小为5GB
st._config.set_option('server.maxUploadSize', 5000)

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
    .warning-box {
        background-color: #f8d7da;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #dc3545;
    }
    .metadata-table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
    }
    .metadata-table th, .metadata-table td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }
    .metadata-table th {
        background-color: #f2f2f2;
    }
</style>
""", unsafe_allow_html=True)


class WSIAnalyzer:
    """WSI文件分析器 - Streamlit优化版"""

    def __init__(self):
        self.progress_bar = None
        self.status_text = None

    def set_progress_elements(self, progress_bar, status_text):
        """设置进度条和状态文本元素"""
        self.progress_bar = progress_bar
        self.status_text = status_text

    def update_progress(self, progress, text):
        """更新进度"""
        if self.progress_bar:
            self.progress_bar.progress(progress)
        if self.status_text:
            self.status_text.text(text)

    def analyze_wsi(self, wsi_path, max_thumbnail_size=800):
        """分析WSI文件"""
        start_time = time.time()

        try:
            # 检查文件是否存在
            if not os.path.exists(wsi_path):
                return {"success": False, "error": f"文件不存在: {wsi_path}"}

            # 检查文件大小
            file_size = os.path.getsize(wsi_path) / (1024 ** 3)  # GB
            self.update_progress(0.1, f"文件大小: {file_size:.2f} GB")

            if file_size == 0:
                return {"success": False, "error": "文件大小为0"}

            # 打开WSI文件
            slide = openslide.OpenSlide(wsi_path)
            self.update_progress(0.3, "WSI文件打开成功")

            # 收集分析结果
            analysis_result = {
                "success": True,
                "filename": os.path.basename(wsi_path),
                "file_size_gb": round(file_size, 2),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "levels": [],
                "properties": {},
                "thumbnail_generated": False
            }

            # 基本信息
            analysis_result["format"] = str(slide.detect_format(wsi_path)) if slide.detect_format(
                wsi_path) else "Unknown"
            analysis_result["level_count"] = int(slide.level_count)
            analysis_result["dimensions_level0"] = str(slide.level_dimensions[0])
            analysis_result["downsamples"] = [float(x) for x in slide.level_downsamples]

            self.update_progress(0.5, "基本信息获取完成")

            # 层级信息
            for i in range(slide.level_count):
                width, height = slide.level_dimensions[i]
                downsample = slide.level_downsamples[i]
                level_info = {
                    'level': i,
                    'width': width,
                    'height': height,
                    'downsample': downsample,
                    'total_pixels': width * height
                }
                analysis_result["levels"].append(level_info)

            # 元数据
            interesting_properties = [
                'openslide.mpp-x', 'openslide.mpp-y',
                'openslide.objective-power',
                'openslide.vendor',
                'openslide.comment',
                'tiff.ImageDescription'
            ]

            for prop in interesting_properties:
                if prop in slide.properties:
                    analysis_result["properties"][prop] = slide.properties[prop]

            # 自动选择最佳层级
            optimal_level = self.select_optimal_level(slide, max_pixels=2000 * 2000)
            self.update_progress(0.7, f"选择层级 {optimal_level} 生成缩略图")

            # 生成缩略图
            thumbnail = self.generate_thumbnail(slide, optimal_level, max_thumbnail_size)
            if thumbnail:
                analysis_result["thumbnail"] = thumbnail
                analysis_result["thumbnail_size"] = thumbnail.size
                analysis_result["thumbnail_generated"] = True
                self.update_progress(0.9, "缩略图生成成功")

            # 性能统计
            elapsed_time = time.time() - start_time
            analysis_result["processing_time"] = round(elapsed_time, 2)

            slide.close()
            self.update_progress(1.0, f"分析完成，耗时: {elapsed_time:.2f}秒")

            return analysis_result

        except openslide.OpenSlideError as e:
            return {"success": False, "error": f"OpenSlide错误: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"错误: {type(e).__name__}: {str(e)}"}

    def select_optimal_level(self, slide, max_pixels=2000 * 2000):
        """选择最优层级"""
        # 优先选择像素数小于max_pixels的最高分辨率层级
        for i in range(slide.level_count):
            width, height = slide.level_dimensions[i]
            if width * height <= max_pixels:
                return i
        # 如果所有层级都太大，返回最低分辨率层级
        return slide.level_count - 1

    def generate_thumbnail(self, slide, level, max_size):
        """生成缩略图"""
        try:
            level_size = slide.level_dimensions[level]

            thumbnail = slide.read_region((0, 0), level, level_size)
            thumbnail = thumbnail.convert("RGB")

            # 计算缩放比例，保持宽高比
            original_width, original_height = thumbnail.size
            ratio = min(max_size / original_width, max_size / original_height)

            if ratio < 1:  # 需要缩小
                new_size = (int(original_width * ratio), int(original_height * ratio))
                thumbnail = thumbnail.resize(new_size, Image.Resampling.LANCZOS)

            return thumbnail

        except Exception as e:
            st.error(f"生成缩略图失败: {str(e)}")
            return None


def calculate_plnm_score(lvi, tumor_budding, pdcs_level, histologic_grade2, sm2):
    """计算PLNM分数"""
    score = lvi * 4 + tumor_budding * 3 + pdcs_level * 2 + histologic_grade2 * 3 + sm2 * 1
    return score


def display_analysis_results(analysis_result):
    """显示分析结果"""
    if not analysis_result["success"]:
        st.error(f"分析失败: {analysis_result['error']}")
        return

    # 创建两列布局
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📊 WSI文件详细信息")

        # 基本信息表格
        st.markdown("**基本信息**")
        basic_info = {
            "文件名": analysis_result["filename"],
            "文件大小": f"{analysis_result['file_size_gb']} GB",
            "分析时间": analysis_result["timestamp"],
            "处理耗时": f"{analysis_result['processing_time']} 秒",
            "文件格式": analysis_result["format"],
            "层级数量": analysis_result["level_count"],
            "基准层尺寸": analysis_result["dimensions_level0"]
        }

        for key, value in basic_info.items():
            st.write(f"**{key}:** {value}")

        # 层级信息
        st.markdown("**层级信息**")
        levels_data = []
        for level_info in analysis_result["levels"]:
            levels_data.append({
                "层级": level_info["level"],
                "宽度": level_info["width"],
                "高度": level_info["height"],
                "降采样": f"{level_info['downsample']:.2f}x",
                "总像素": f"{level_info['total_pixels']:,}"
            })

        # 显示前几个层级（避免表格太长）
        st.table(levels_data[:5])
        if len(levels_data) > 5:
            st.info(f"还有 {len(levels_data) - 5} 个层级未显示")

        # 元数据
        if analysis_result["properties"]:
            st.markdown("**元数据**")
            for prop, value in analysis_result["properties"].items():
                st.write(f"**{prop}:** {value}")

    with col2:
        st.subheader("🖼️ WSI缩略图")
        if analysis_result["thumbnail_generated"]:
            thumbnail = analysis_result["thumbnail"]
            st.image(thumbnail, caption=f"缩略图尺寸: {thumbnail.size[0]} × {thumbnail.size[1]}",
                     use_container_width=True)

            # 提供下载链接
            buf = io.BytesIO()
            thumbnail.save(buf, format="JPEG", quality=90)
            buf.seek(0)

            st.download_button(
                label="📥 下载缩略图",
                data=buf,
                file_name=f"{os.path.splitext(analysis_result['filename'])[0]}_thumbnail.jpg",
                mime="image/jpeg"
            )
        else:
            st.warning("缩略图生成失败")


def main():
    # 页面标题
    st.markdown('<div class="main-header">🔬 病理切片分析平台</div>', unsafe_allow_html=True)

    # 初始化分析器
    analyzer = WSIAnalyzer()

    # 侧边栏 - 用户输入
    with st.sidebar:
        st.header("🧪 病理参数设置")

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
        st.header("📁 WSI文件上传")
        uploaded_file = st.file_uploader(
            "上传全切片图像(WSI):",
            type=['svs', 'tif', 'tiff', 'ndpi', 'scn', 'mrxs', 'vms', 'vmu'],
            help="支持 .svs, .tif, .tiff, .ndpi, .scn, .mrxs, .vms, .vmu 格式"
        )

        # 高级设置
        with st.expander("⚙️ 高级设置"):
            max_thumbnail_size = st.slider("缩略图最大尺寸", 400, 1200, 800, 50)
            auto_open = st.checkbox("自动显示详细分析", value=True)

    # 主内容区域
    # PLNM Score计算结果显示
    plnm_score = calculate_plnm_score(lvi, tumor_budding, pdcs_level, histologic_grade2, sm2)

    st.markdown(f"""
    <div class="score-box">
        <h3>PLNM Score Calculation = LVI × 4 + Tumor budding × 3 + PDCs level × 2 + Histologic grade2 × 3 + SM2 × 1</h3>
        <h2 style="text-align: center; color: #1f77b4;">PLNM Score = {plnm_score}</h2>
    </div>
    """, unsafe_allow_html=True)

    # WSI文件分析
    if uploaded_file is not None:
        # 创建进度指示器
        progress_bar = st.progress(0)
        status_text = st.empty()
        analyzer.set_progress_elements(progress_bar, status_text)

        # 保存上传的文件到临时位置
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            # 分析WSI文件
            analysis_result = analyzer.analyze_wsi(tmp_path, max_thumbnail_size)

            # 显示分析结果
            display_analysis_results(analysis_result)

            # 显示成功消息
            if analysis_result["success"]:
                st.success(f"✅ 分析完成！文件 '{uploaded_file.name}' 已成功处理。")

                # 显示详细分析报告（可选）
                if auto_open:
                    with st.expander("📋 详细分析报告"):
                        st.json(analysis_result)

        except Exception as e:
            st.error(f"❌ 分析过程中发生错误: {str(e)}")

        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except:
                pass

            # 清除进度指示器
            progress_bar.empty()
            status_text.empty()

    else:
        # 没有上传文件时的提示
        st.info("ℹ️ 请在左侧上传WSI文件以进行分析")

        # 创建两列占位
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("📊 WSI文件基本信息")
            st.markdown("""
            <div class="info-box">
                <h4>等待上传文件...</h4>
                <p>上传WSI文件后，将显示以下信息：</p>
                <ul>
                    <li>文件基本信息（格式、大小、层级数）</li>
                    <li>各层级尺寸和降采样信息</li>
                    <li>扫描分辨率和元数据</li>
                    <li>高质量缩略图</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.subheader("🖼️ WSI缩略图")
            st.image(Image.new('RGB', (400, 300), color='lightgray'),
                     caption="等待上传文件", use_container_width=True)

        # 使用说明
        with st.expander("📖 使用说明"):
            st.markdown("""
            ### 使用步骤：
            1. **设置病理参数** - 在左侧边栏选择相应的病理参数
            2. **上传WSI文件** - 点击"Browse files"或拖拽文件到上传区域
            3. **查看结果** - 系统将自动分析文件并显示结果

            ### 支持的文件格式：
            - .svs (Aperio)
            - .tif, .tiff (TIFF)
            - .ndpi (Hamamatsu)
            - .scn (Leica)
            - .mrxs (MIRAX)
            - .vms, .vmu (Philips)

            ### 功能特点：
            - 智能层级选择，优化内存使用
            - 详细的元数据提取
            - 高质量缩略图生成
            - 支持大文件处理（最大5GB）
            """)

    # 页脚信息
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666;'>病理切片分析平台 • 基于OpenSlide和Streamlit</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    # 检查openslide是否可用
    try:
        import openslide

        main()
    except ImportError:
        st.error("""
        **❌ 错误: openslide-python 库未安装**

        请使用以下命令安装所需依赖：
        ```bash
        pip install openslide-python streamlit Pillow
        ```

        另外，您还需要安装系统级的OpenSlide库：
        - **Windows**: 下载OpenSlide Win64并设置环境变量
        - **Linux**: `sudo apt-get install openslide-tools`
        - **macOS**: `brew install openslide`

        对于Streamlit Cloud部署，请确保在requirements.txt中包含：
        ```
        openslide-python
        Pillow
        ```
        """)
