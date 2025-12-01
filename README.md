# Global Fishing Watch 縮圖工具

一組腳本，用來：
- 取得 MVT feature 資料（`get_features.py`）
- 從 feature 產生縮圖 URL（`generate_img_urls.py`）
- 使用 Token 下載縮圖（`get_images_raw.py`，會存成 `.bin` JSON）
- 將 `.bin` 內的 base64 PNG 轉檔（`convert_bins_to_png.py`）

## 環境
- Python 虛擬環境在 `env/`，若需要：`pip install -r requirements.txt`
- 將 API Token 寫入 `.env`：`GFW_TOKEN=<token>`（`get_features.py`、`get_images_raw.py` 會讀取）

## 工作流程
1) 產生縮圖 URL：  
   `python generate_img_urls.py`  
   - 預設讀取 `features.json`，輸出 `img_urls.json`
2) 下載縮圖回應（需 Token）：  
   `python get_images_raw.py --token $GFW_TOKEN`  
   - 讀取 `img_urls.json`，在 `images/` 產生 `.bin`
3) 將 `.bin` 轉成 PNG：  
   `python convert_bins_to_png.py --input-dir images --output-dir images`
4) （可選）取得並解碼 MVT tile：  
   `python get_features.py --url <tile_url> --token $GFW_TOKEN --save-json features.json`

## 說明
- `img_urls.json` 內容為縮圖 URL 陣列，格式 `https://gateway.api.globalfishingwatch.org/v3/thumbnail/<feature_id>?dataset=public-global-sentinel2-thumbnails:v3.0`
- 縮圖端點回傳的 `.bin` 是 JSON 陣列，欄位 `data` 為 `image/png;base64,...`；`convert_bins_to_png.py` 會解碼並輸出 `.png`
- `.gitignore` 已忽略 `images/`、`img_urls.json`、`features.json` 等輸出
