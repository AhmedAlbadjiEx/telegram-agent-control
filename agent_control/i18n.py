"""Small, dependency-free message catalog for the Telegram interface."""

SUPPORTED_LANGUAGES = ("en", "ar")

MESSAGES = {
    "en": {
        "help": """Remote Agent Control
/agents — configured agents
/projects — configured projects
/new <agent> <project> <instruction> — start a conversation
/sessions — your latest conversations
/status <session> — state and recent output
/logs <session> — last 3000 characters
/history <session> — recent runs
/ask <session> <instruction> — resume after a run finishes
/stop <session> — stop the active run
/language <en|ar> — change the interface language
/help — this message

Example: /new codex myapp explain this repository
Session IDs are shown when a run starts. Only private chats are accepted.""",
        "agents": "Agents: {items}",
        "projects": "Projects: {items}",
        "started": "Started {agent} on {project}.\nSession: {session} • run {run}\n/stop {session}",
        "session_line": "{session} · {agent}/{project} · {status}",
        "no_sessions": "No sessions yet. Use /new.",
        "resuming": "Resuming {session} • run {run}",
        "stop_requested": "Stop requested for {session}.",
        "history_line": "Run {run}: {status} (exit {exit_code})",
        "no_runs": "No runs.",
        "no_output": "No output yet.",
        "status": "{session} · {agent}/{project}\nState: {status}\n{output}",
        "unknown_command": "Use /help for commands. Send follow-ups with /ask <session> <instruction>.",
        "language_help": "Interface language: {language}. Change it with /language en or /language ar.",
        "language_changed": "Interface language changed to English.",
        "language_invalid": "Choose a supported language: /language en or /language ar.",
        "progress": "Session {session} • {status}\n{output}",
        "finished": "Session {session} • {status}\n{output}\n\n/ask {session} your next instruction",
        "error_usage_new": "Usage: /new <agent> <project> <instruction>",
        "error_unknown_alias": "Unknown alias. Use /agents and /projects.",
        "error_usage_session": "Usage: {command} <session>{suffix}",
        "error_usage_ask": "Usage: /ask <session> <instruction>",
        "error_no_native": "No resumable conversation ID was captured. Start a new session with /new.",
        "error_session_not_found": "Session not found.",
        "error_project_removed": "Project is no longer configured.",
        "error_busy": "Server is busy. Try again after a run finishes.",
        "error_project_active": "That project already has an active run.",
        "error_project_missing": "Project directory is missing or has changed.",
        "error_directory_active": "That directory already has an active run.",
        "error_prompt": "Provide a prompt between 1 and 12000 characters.",
        "error_agent_removed": "Agent is no longer configured.",
        "error_session_running": "Session is running. Stop it or wait before sending a follow-up.",
        "error_not_running": "Session is not running.",
    },
    "ar": {
        "help": """التحكم بالوكلاء عن بُعد
/agents — الوكلاء المهيّؤون
/projects — المشاريع المهيّأة
/new <agent> <project> <instruction> — بدء محادثة جديدة
/sessions — أحدث محادثاتك
/status <session> — الحالة وأحدث المخرجات
/logs <session> — آخر 3000 محرف
/history <session> — أحدث التشغيلات
/ask <session> <instruction> — متابعة محادثة بعد انتهاء التشغيل
/stop <session> — إيقاف التشغيل النشط
/language <en|ar> — تغيير لغة الواجهة
/help — عرض هذه الرسالة

مثال: /new codex myapp اشرح هذا المستودع
يظهر معرّف المحادثة عند بدء التشغيل. تُقبل المحادثات الخاصة فقط.""",
        "agents": "الوكلاء: {items}",
        "projects": "المشاريع: {items}",
        "started": "بدأ تشغيل {agent} على {project}.\nالمحادثة: {session} • التشغيل {run}\n/stop {session}",
        "session_line": "{session} · {agent}/{project} · {status}",
        "no_sessions": "لا توجد محادثات بعد. استخدم /new.",
        "resuming": "تجري متابعة {session} • التشغيل {run}",
        "stop_requested": "طُلب إيقاف {session}.",
        "history_line": "التشغيل {run}: {status} (رمز الخروج {exit_code})",
        "no_runs": "لا توجد تشغيلات.",
        "no_output": "لا توجد مخرجات بعد.",
        "status": "{session} · {agent}/{project}\nالحالة: {status}\n{output}",
        "unknown_command": "استخدم /help لعرض الأوامر. أرسل المتابعة باستخدام /ask <session> <instruction>.",
        "language_help": "لغة الواجهة: {language}. غيّرها باستخدام /language en أو /language ar.",
        "language_changed": "تم تغيير لغة الواجهة إلى العربية.",
        "language_invalid": "اختر لغة مدعومة: /language en أو /language ar.",
        "progress": "المحادثة {session} • {status}\n{output}",
        "finished": "المحادثة {session} • {status}\n{output}\n\n/ask {session} اكتب توجيهك التالي",
        "error_usage_new": "الاستخدام: /new <agent> <project> <instruction>",
        "error_unknown_alias": "اسم غير معروف. استخدم الأمرين /agents و /projects.",
        "error_usage_session": "الاستخدام: {command} <session>{suffix}",
        "error_usage_ask": "الاستخدام: /ask <session> <instruction>",
        "error_no_native": "لم يُلتقط معرّف محادثة قابل للمتابعة. ابدأ محادثة جديدة باستخدام /new.",
        "error_session_not_found": "المحادثة غير موجودة.",
        "error_project_removed": "لم يعد المشروع مهيّأً.",
        "error_busy": "الخادم مشغول. حاول بعد انتهاء أحد التشغيلات.",
        "error_project_active": "لدى هذا المشروع تشغيل نشط بالفعل.",
        "error_project_missing": "مجلد المشروع مفقود أو تغيّر.",
        "error_directory_active": "لدى هذا المجلد تشغيل نشط بالفعل.",
        "error_prompt": "أدخل توجيهاً يتراوح طوله بين 1 و12000 محرف.",
        "error_agent_removed": "لم يعد الوكيل مهيّأً.",
        "error_session_running": "المحادثة قيد التشغيل. أوقفها أو انتظر قبل إرسال متابعة.",
        "error_not_running": "المحادثة ليست قيد التشغيل.",
    },
}

STATUSES = {
    "en": {
        "new": "new", "running": "running", "completed": "completed", "failed": "failed",
        "stopped": "stopped", "timed_out": "timed out", "output_limit": "output limit",
        "interrupted": "interrupted",
    },
    "ar": {
        "new": "جديدة", "running": "قيد التشغيل", "completed": "مكتملة", "failed": "فاشلة",
        "stopped": "متوقفة", "timed_out": "انتهت مهلتها", "output_limit": "تجاوزت حد المخرجات",
        "interrupted": "منقطعة",
    },
}

ERROR_KEYS = {
    "Session not found.": "error_session_not_found",
    "Project is no longer configured.": "error_project_removed",
    "Server is busy. Try again after a run finishes.": "error_busy",
    "That project already has an active run.": "error_project_active",
    "Project directory is missing or has changed.": "error_project_missing",
    "That directory already has an active run.": "error_directory_active",
    "Provide a prompt between 1 and 12000 characters.": "error_prompt",
    "Agent is no longer configured.": "error_agent_removed",
    "Session is running. Stop it or wait before sending a follow-up.": "error_session_running",
    "Session is not running.": "error_not_running",
}


def normalize_language(value):
    value = (value or "").strip().lower().replace("_", "-")
    return "ar" if value == "ar" or value.startswith("ar-") else "en"


def text(language, key, **values):
    return MESSAGES[normalize_language(language)][key].format(**values)


def status_text(language, status):
    language = normalize_language(language)
    return STATUSES[language].get(status, status)


def error_text(language, message):
    key = ERROR_KEYS.get(message)
    return text(language, key) if key else message
