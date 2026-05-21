import os
import asyncio
import httpx
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List
from google import genai
from google.genai import types

def load_env():
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    except FileNotFoundError:
        print("ℹ️ กำลังรันบน Cloud ใช้คีย์จากระบบ (Secrets)")

class ContentIdea(BaseModel):
    topic: str = Field(description="หัวข้อเรื่องลึกลับหรือคดีปริศนา แปลเป็นภาษาไทย")
    hook: str = Field(description="ประโยคเปิดคลิป 3 วิแรกแบบระทึกขวัญชวนสงสัย (ภาษาไทย)")
    script_steps: List[str] = Field(description="สคริปต์การเล่าเรื่องทีละฉาก ค่อยๆ เผยความลับให้น่าติดตาม")

class TrendReport(BaseModel):
    overview: str = Field(description="สรุปภาพรวมว่าตอนนี้คนกำลังสนใจเรื่องอะไร (ภาษาไทย)")
    ideas: List[ContentIdea] = Field(description="ไอเดียคอนเทนต์ 3 รายการ")

async def fetch_trends():
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "X-Subscription-Token": os.getenv("BRAVE_API_KEY")}
    # ค้นหาเรื่องลึกลับ คดีปริศนา หรือเรื่องแปลกที่เป็นกระแส (ขยายเวลาเป็นพ้น 1 สัปดาห์ 'pw' เพื่อให้ได้เนื้อหาที่แน่นขึ้น)
    params = {
        "q": "trending unsolved mysteries OR viral creepy stories OR bizarre history facts", 
        "freshness": "pw", 
        "count": 10
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        results = [f"Title: {item.get('title')}\nInfo: {item.get('description')}" for item in data.get('web', {}).get('results', [])]
        return "\n---\n".join(results)

def generate_content(raw_data: str):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    # อัปเกรดคำสั่งเป็น จิตวิญญาณนักเล่าเรื่องระทึกขวัญระดับฮอลลีวูด 🎬
    prompt = (
        "You are a master of Cinematic Suspense and Mystery Storytelling. Analyze the following trending data "
        "and select the single most chilling, mind-bending, or bizarre mystery story. "
        "Create 3 viral short-form video (TikTok/Shorts) content ideas and highly detailed scripts in THAI. "
        "Apply these psychological storytelling rules strictly:\n\n"
        
        "1. THE HOOK (First 3 seconds): Open with a shocking, unexplainable fact, a creepy question, or a statement that violates common sense. "
        "Never say hello or introduce the channel. Start the story immediately. (e.g., 'นี่คือภาพถ่ายสุดท้ายของนักท่องเที่ยว 9 คน ก่อนที่พวกเขาจะกลายเป็นศพในสภาพที่ตาทั้งสองข้างหายไป...')\n"
        
        "2. SHOW, DON'T TELL (Atmospheric Details): Instead of just saying 'it was scary', use sensory and atmospheric words in Thai to build dread and curiosity "
        "(e.g., 'เสียงเคาะประตูตอนตี 3', 'บันทึกหน้าสุดท้ายที่ถูกฉีกขาด', 'รอยเท้าที่สิ้นสุดลงตรงหน้าผา'). Keep sentences short, punchy, and fast-paced.\n"
        
        "3. THE CLIFFHANGER / PLOT TWIST (The End): Never wrap up the story nicely. End with an eerie unanswered question, a chilling realization, "
        "or a cliffhanger that forces the viewer to comment their theories, share, or rewatch the video to find clues.\n\n"
        
        f"MYSTERY DATA:\n{raw_data}"
    )
    
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TrendReport,
            temperature=0.8, # เพิ่มความคิดสร้างสรรค์และโทนเสียงให้ดูลึกลับขึ้น
        )
    )
    return response.text

def save_to_file(report: TrendReport):
    if not os.path.exists("outputs"): os.makedirs("outputs")
    now = datetime.now()
    filename = f"outputs/trend_{now.strftime('%Y%m%d_%H%M%S')}.md"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# 🔥 AI TREND REPORT ({now.strftime('%Y-%m-%d %H:%M')})\n\n**ภาพรวม:** {report.overview}\n\n---\n\n")
        for idx, idea in enumerate(report.ideas, 1):
            f.write(f"## 🎬 ไอเดียที่ {idx}: {idea.topic}\n> **Hook (3 วิแรก):** {idea.hook}\n\n**📝 สคริปต์:**\n")
            for step in idea.script_steps: f.write(f"- {step}\n")
            f.write("\n---\n\n")
    return filename

# ฟังก์ชันส่ง Telegram 🚀
async def send_telegram_notify(report: TrendReport):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("⚠️ ไม่พบ TELEGRAM_BOT_TOKEN หรือ CHAT_ID ข้ามการแจ้งเตือน")
        return
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    msg = f"🔥 บอทคิดคอนเทนต์เสร็จแล้ว!\n\n"
    for idx, idea in enumerate(report.ideas, 1):
        msg += f"🎬 {idx}. {idea.topic}\n"
    msg += "\n👉 เข้าไปดูสคริปต์เต็มๆ ได้ที่ GitHub เลย!"

    payload = {"chat_id": chat_id, "text": msg}

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        if response.status_code == 200:
            print("✅ ส่งแจ้งเตือนเข้า Telegram สำเร็จ!")
        else:
            print(f"❌ ส่ง Telegram ไม่สำเร็จ: {response.text}")

async def automation_job():
    try:
        raw_data = await fetch_trends()
        result_json_string = generate_content(raw_data)
        report = TrendReport.model_validate_json(result_json_string)
        save_to_file(report)
        await send_telegram_notify(report)
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")

async def main():
    load_env()
    await automation_job()
    print("\n🏁 จบการทำงานรอบนี้...")

if __name__ == "__main__":
    asyncio.run(main())
