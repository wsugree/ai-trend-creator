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
    topic: str = Field(description="หัวข้อคอนเทนต์ที่กำลังเป็นกระแส แปลเป็นภาษาไทย")
    hook: str = Field(description="ประโยคเปิดคลิป 3 วินาทีแรกที่ดึงดูดใจวัยรุ่น (ภาษาไทย)")
    script_steps: List[str] = Field(description="สคริปต์หรือลำดับการเล่าเรื่องแบบสั้นๆ ทีละฉาก")

class TrendReport(BaseModel):
    overview: str = Field(description="สรุปภาพรวมว่าตอนนี้คนกำลังสนใจเรื่องอะไร (ภาษาไทย)")
    ideas: List[ContentIdea] = Field(description="ไอเดียคอนเทนต์ 3 รายการ")

async def fetch_trends():
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "X-Subscription-Token": os.getenv("BRAVE_API_KEY")}
    params = {"q": "latest AI and tech trends", "freshness": "pd", "count": 10}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        results = [f"Title: {item.get('title')}\nInfo: {item.get('description')}" for item in data.get('web', {}).get('results', [])]
        return "\n---\n".join(results)

def generate_content(raw_data: str):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = (
        "You are an expert Content Creator. Analyze the following trending news. "
        "Synthesize what people are interested in right now, and create 3 viral short-form video "
        "(TikTok/Shorts) content ideas based on these trends. Make it highly engaging.\n\n"
        f"TRENDING DATA:\n{raw_data}"
    )
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=TrendReport, temperature=0.7
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
