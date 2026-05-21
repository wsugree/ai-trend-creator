import os
import asyncio
import httpx
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List
from google import genai
from google.genai import types

# 1. โหลด API Keys
def load_env():
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    except FileNotFoundError:
        print("❌ ไม่พบไฟล์ .env")
        exit(1)

# 2. โครงสร้างข้อมูล (Data Structure)
class ContentIdea(BaseModel):
    topic: str = Field(description="หัวข้อคอนเทนต์ที่กำลังเป็นกระแส แปลเป็นภาษาไทย")
    hook: str = Field(description="ประโยคเปิดคลิป 3 วินาทีแรกที่ดึงดูดใจวัยรุ่น (ภาษาไทย)")
    script_steps: List[str] = Field(description="สคริปต์หรือลำดับการเล่าเรื่องแบบสั้นๆ ทีละฉาก")

class TrendReport(BaseModel):
    overview: str = Field(description="สรุปภาพรวมว่าตอนนี้คนกำลังสนใจเรื่องอะไร (ภาษาไทย)")
    ideas: List[ContentIdea] = Field(description="ไอเดียคอนเทนต์ 3 รายการ")

# 3. ดึงข้อมูล
async def fetch_trends():
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": os.getenv("BRAVE_API_KEY")
    }
    params = {"q": "latest AI and tech trends", "freshness": "pd", "count": 10}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get('web', {}).get('results', []):
            results.append(f"Title: {item.get('title')}\nInfo: {item.get('description')}")
        return "\n---\n".join(results)

# 4. วิเคราะห์ด้วย AI
def generate_content(raw_data: str):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    prompt = (
        "You are an expert Content Creator. Analyze the following trending news. "
        "Synthesize what people are interested in right now, and create 3 viral short-form video "
        "(TikTok/Shorts) content ideas based on these trends. Make it highly engaging.\n\n"
        f"TRENDING DATA:\n{raw_data}"
    )
    # ใช้โมเดลล่าสุด (หากมีปัญหาให้เปลี่ยนกลับเป็นโมเดลที่คุณรันผ่าน)
    response = client.models.generate_content(
        model='gemini-2.5-flash', 
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TrendReport,
            temperature=0.7,
        )
    )
    return response.text

# 5. ฟังก์ชันบันทึกไฟล์ (ใหม่! 🌟)
def save_to_file(report: TrendReport):
    # สร้างโฟลเดอร์ชื่อ outputs ถ้ายังไม่มี
    if not os.path.exists("outputs"):
        os.makedirs("outputs")
        
    # สร้างชื่อไฟล์ตามวันเวลาปัจจุบัน
    now = datetime.now()
    filename = f"outputs/trend_{now.strftime('%Y%m%d_%H%M%S')}.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# 🔥 AI TREND REPORT ({now.strftime('%Y-%m-%d %H:%M')})\n\n")
        f.write(f"**ภาพรวม:** {report.overview}\n\n")
        f.write("---\n\n")
        
        for idx, idea in enumerate(report.ideas, 1):
            f.write(f"## 🎬 ไอเดียที่ {idx}: {idea.topic}\n")
            f.write(f"> **Hook (3 วิแรก):** {idea.hook}\n\n")
            f.write("**📝 สคริปต์:**\n")
            for step in idea.script_steps:
                f.write(f"- {step}\n")
            f.write("\n---\n\n")
            
    return filename

# 6. วงจรการทำงานอัตโนมัติ (The Automation Loop 🔄)
async def automation_job():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 เริ่มต้นรอบการทำงานใหม่...")
    try:
        raw_data = await fetch_trends()
        result_json_string = generate_content(raw_data)
        report = TrendReport.model_validate_json(result_json_string)
        
        # บันทึกลงไฟล์
        saved_file = save_to_file(report)
        print(f"✅ สร้างคอนเทนต์สำเร็จ! บันทึกไฟล์ไว้ที่: {saved_file}")
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในรอบนี้: {e}")

async def main():
    load_env()
    print("=======================================")
    print("☁️ AI Trend Automator (Cloud Mode) ☁️")
    print("=======================================\n")
    
    # รันการทำงานแค่ 1 รอบ แล้วปิดตัวเอง (Cloud จะเป็นคนสั่งรันซ้ำเอง)
    await automation_job()
    print("\n🏁 จบการทำงานรอบนี้...")

if __name__ == "__main__":
    asyncio.run(main())