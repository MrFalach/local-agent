# local-agent

פועל עם קלוד קוד ומנתב אוטומטית כל בקשה — משימות קוד פשוטות הולכות למודל מקומי על המחשב שלך (חינם), משימות מורכבות הולכות לקלוד בענן.

**התוצאה:** אתה עובד בדיוק כמו תמיד — אבל רוב ייצור הקוד לא עולה כלום.

---

## איך זה עובד

```
אתה שואל קלוד קוד משהו
           ↓
       local-agent
      ↙            ↘
qwen2.5-coder    קלוד ענן
 (מקומי, חינם)   (רק לקשה)
```

**מקומי** — כתיבת קוד, ריפקטורינג, בדיקות, תיעוד → ~15 שניות, עולה אפס

**ענן** — ארכיטקטורה, דיבוג עמוק, אבטחה, שאלות "למה" → כשזה באמת שווה

---

## התקנה

**דרישות:** קלוד קוד, אולמה, פייתון 3.10+

```bash
# 1. הורד מודלים
ollama pull qwen2.5-coder:7b
ollama pull gemma4:12b

# 2. שכפל והתקן
git clone https://github.com/MrFalach/local-agent.git
cd local-agent
pip install -r requirements.txt

# 3. הגדר
cp .env.example .env
# ערוך .env והכנס ANTHROPIC_API_KEY מ-console.anthropic.com

# 4. רשום בקלוד קוד
claude mcp add local-agent python3 /path/to/local-agent/server.py

# 5. פתח מחדש קלוד קוד — הכלים פעילים
```

---

## כלים

| כלי | מה עושה |
|-----|---------|
| `local-agent:dev` | משימת פיתוח — ניתוב אוטומטי |
| `local-agent:ask` | שאלה טכנית — ניתוב אוטומטי |
| `local-agent:local` | כפה מקומי |
| `local-agent:cloud` | כפה ענן |

---

## הגדרות

קובץ `.env`:

```env
ANTHROPIC_API_KEY=...
LOCAL_MODEL=qwen2.5-coder:7b       # מודל קוד מהיר
LOCAL_MODEL_GENERAL=gemma4:12b     # מודל כללי
CLOUD_MODEL=claude-sonnet-4-6      # ענן
```

כל מודל שאולמה תומך בו עובד — רק שנה את השם.

---

## מבנה

```
server.py      שרת MCP
router.py      לוגיקת ניתוב
providers.py   חיבור לאולמה ולאנתרופיק
CLAUDE.md      הוראות לקלוד קוד
```
