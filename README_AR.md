# AYMEN Phone Service

نسخة أولية لبرنامج Windows لصيانة الهواتف والبحث عن مصادر النظام الرسمية.

## التشغيل
1. ثبّت Python 3.10 أو أحدث على Windows.
2. افتح مجلد المشروع في Terminal.
3. نفّذ:
   ```bat
   py -m pip install -r requirements.txt
   py main.py
   ```

## إنشاء نسخة EXE
شغّل `build_windows.bat`. بعد اكتمال البناء ستجد البرنامج داخل:
`dist\AYMEN_Phone_Service\AYMEN_Phone_Service.exe`

## الوظائف الحالية
- واجهة عربية/فرنسية.
- اختيار الشركة وإدخال طراز الجهاز.
- فتح بحث ويب موجه للعثور على مصادر Firmware والدعم الرسمي.
- فتح صفحات دعم الشركات الرسمية.
- اكتشاف أجهزة Android عبر ADB إذا كان ADB مثبتًا ومتاحًا في PATH.
- روابط لأدوات Android الرسمية وإرشادات استعادة iPhone الرسمية.

## حدود النسخة الأولية
هذه ليست أداة تفليش شاملة بعد. لا تنفّذ كتابة Firmware أو فتح Bootloader أو إزالة أقفال حماية. توفر ملفات النظام يختلف حسب الطراز والمنطقة، ويجب التحقق من التوافق والتوقيع ومصدر الملف قبل أي عملية. استعادة iPhone تتم عبر Apple Devices أو أدوات Apple الرسمية وقد تمسح البيانات.

## مصادر رسمية
- Android SDK Platform-Tools: https://developer.android.com/tools/releases/platform-tools
- Apple Restore Help: https://support.apple.com/en-us/118106
- Samsung Support: https://www.samsung.com/support/
- Xiaomi Support: https://www.mi.com/global/support/
- Google Pixel Help: https://support.google.com/pixelphone/
