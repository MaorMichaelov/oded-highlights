# חיבור יוטיוב ללקוחות בלי דומיין (מצב בדיקה של גוגל)

**בקיצור:** גוגל מאפשרת אפליקציה במצב "Testing" ללא אימות ובלי דומיין, עד **100 משתמשים** שאתה מוסיף ידנית. כל לקוח מחבר את ערוץ היוטיוב שלו, ומחבר מחדש אחת ל-7 ימים. זה מספיק לפיילוט.

האימות המלא של גוגל (הסרת מגבלת 100 והחיבור מחדש) דורש דומיין בבעלותך. מעבר ל-`workers.dev` אי אפשר לאמת. כשיהיה דומיין (בערך דולר עד עשרה בשנה), נגיש בקשה.

## מה צריך לעשות (פעם אחת, כ-10 דקות, בחשבון הגוגל שלך)
1. https://console.cloud.google.com → פרויקט חדש (למשל `studio-clips`).
2. APIs & Services → Library → להפעיל **YouTube Data API v3**.
3. APIs & Services → OAuth consent screen: User type **External**, שם אפליקציה, אימייל תמיכה (שלך), **Publishing status: Testing**. Scopes: `youtube.upload` ו-`youtube.readonly`. Test users: להוסיף את אימיילי הגוגל של הלקוחות (עד 100).
4. Credentials → Create credentials → OAuth client ID → **Web application**. Authorized redirect URI בדיוק:
   `https://studio-app.odedhl.workers.dev/studio/yt/callback`
5. להעתיק את **Client ID** ואת **Client secret**.
6. ב-Cloudflare: Workers & Pages → `studio-app` → Settings → Variables and Secrets → להוסיף כסודות: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, ו-`STUDIO_ENC_KEY` (מחרוזת אקראית ארוכה, 32 תווים ומעלה).
   (אל תשלח אותם בצ'אט. אם תרצה שאעשה את זה, תגיד "אשר לך להגדיר מפתחות גוגל" ותשלח אותם בצורה בטוחה.)

אחרי זה כפתור "חבר יוטיוב" באתר יעבוד ללקוחות שברשימת ה-Test users.

## מה עדיין בלי דומיין
- ההעלאה היא רק **טיוטה פרטית** (גם אחרי אימות מלא גוגל מגבילה פרסום ישיר עד ביקורת נוספת).
- מכסה: כ-100 העלאות ביום לפרויקט (משותף לכל הלקוחות).

## אלטרנטיבה ללא גוגל בכלל
הלקוח מוריד את הקליפים מהאתר ומעלה בעצמו. עובד היום.
