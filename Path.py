# 打开网页，在cmd命令界面运行下面一段
# streamlit run C:\Users\30821\Desktop\Pathlogical\Path.py [ARGUMENTS]

import os
import sys
# 设置无头模式，避免GUI相关错误
os.environ['OPENSLIDE_HEADLESS'] = 'True'

import streamlit as st
from PIL import Image
import io
import tempfile
import time
from datetime import datetime
import json

# 尝试导入openslide，如果失败提供友好错误提示
try:
    import openslide
    OPENSLIDE_AVAILABLE = True
except ImportError as e:
    OPENSLIDE_AVAILABLE = False
    st.error(f"❌ OpenSlide导入失败: {str(e)}")
except Exception as e:
    OPENSLIDE_AVAILABLE = False
    st.error(f"❌ OpenSlide初始化错误: {str(e)}")

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
    .warning-box {
        background-color: #f8d7da;
        padding: 15px;
        border-radius: 5px;
        border-left: 5px solid #dc3545;
    }
</style>
""", unsafe_allow_html=True)

class WSIAnalyzer:
    """WSI文件分析器 - Streamlit Cloud兼容版"""

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
        if not OPENSLIDE_AVAILABLE:
            return {"success": False, "error": "OpenSlide不可用"}
            
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
            try:
                analysis_result["format"] = str(slide.detect_format(wsi_path)) if slide.detect_format(wsi_path) else "Unknown"
            except:
                analysis_result["format"] = "Unknown"
                
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

            # 自动选择最佳层级 - 使用更保守的设置
            optimal_level = self.select_optimal_level(slide, max_pixels=1000 * 1000)
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

    def select_optimal_level(self, slide, max_pixels=1000 * 1000):
        """选择最优层级 - 使用更保守的设置"""
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
        if analysis_result["levels"]:
            st.markdown("**层级信息**")
            levels_data = []
            for level_info in analysis_result["levels"][:3]:  # 只显示前3个层级
                levels_data.append({
                    "层级": level_info["level"],
                    "宽度": level_info["width"],
                    "高度": level_info["height"],
                    "降采样": f"{level_info['downsample']:.2f}x"
                })
            st.table(levels_data)

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
                     width='stretch')

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
    # 检查OpenSlide是否可用
    if not OPENSLIDE_AVAILABLE:
        st.error("""
        ## ❌ OpenSlide不可用
        
        当前环境缺少OpenSlide支持。这可能是由于：
        
        - 系统级OpenSlide库未安装
        - 环境配置问题
        
        对于Streamlit Cloud部署，请确保：
        1. 项目根目录有 `packages.txt` 文件，内容为：
        ```
        libopenslide0
        openslide-tools
        ```
        2. 项目根目录有 `requirements.txt` 文件，内容为：
        ```
        streamlit>=1.28.0
        Pillow>=10.0.0
        openslide-python==1.3.1
        ```
        """)
        return

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
                     caption="等待上传文件", width='stretch')

    # 页脚信息
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666;'>病理切片分析平台 • 基于OpenSlide和Streamlit</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    # 设置无头模式
    if 'STREAMLIT_SERVER' in os.environ:
        os.environ['OPENSLIDE_HEADLESS'] = 'True'
    
    main()
