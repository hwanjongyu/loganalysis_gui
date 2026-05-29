# 📖 LogAnalysisGUI Regular Expression Filter Cookbook

This reference guide provides high-performance regular expression (regex) patterns and filtering templates optimized for standard logging systems (Android Logcat, Spring Boot, Nginx Web Logs).

---

## 📱 1. Android ADB Logcat Patterns

When debugging mobile applications, Logcat outputs dense information containing Process IDs (PIDs), Thread IDs (TIDs), Log Levels, and Tags.

### Recommended Filters

| Filter Type | Regex Pattern | Purpose |
| :--- | :--- | :--- |
| **FATAL Exceptions** | `(?i)FATAL EXCEPTION` | Instantly isolate application crashes and unhandled exceptions. |
| **ANR Events** | `(?i)Application Not Responding` | Track Application Not Responding (ANR) lockups. |
| **Garbage Collector** | `\b(GC_CONCURRENT|GC_FOR_ALLOC)\b` | Monitor memory allocations and GC execution pauses. |
| **Tag Isolation** | `^[A-Z]\/\bMyApplicationTag\b` | Include only lines emitted by your specific tag name. |

---

## ☕ 2. Spring Boot / Java Backend Logs

Backend logs capture system lifecycle, database queries, and stack traces.

### Recommended Filters

| Filter Type | Regex Pattern | Purpose |
| :--- | :--- | :--- |
| **NullPointerExceptions** | `(?i)NullPointerException` | Quick isolation of Java NPEs in deep stack traces. |
| **Hikari CP Warnings** | `\bHikariPool\b.*(Timeout|Slow)` | Track database pool bottlenecks and slow queries. |
| **Error Log Levels** | `\b(ERROR|WARN)\b` | Isolate warning and error traces while hiding INFO messages. |
| **Rest Controller Trace** | `\b(POST|GET|PUT|DELETE)\b\s+\/api\/v1` | Trace API controller request methods. |

---

## 🌐 3. Nginx Web Access Logs

Web access logs store client request IPs, paths, response codes, and user-agents.

### Recommended Filters

| Filter Type | Regex Pattern | Purpose |
| :--- | :--- | :--- |
| **Server Errors (5xx)** | `\b5\d{2}\b` | Filter out HTTP 500, 502, 503, 504 server-side faults. |
| **Not Found Paths (404)** | `\b404\b` | Identify broken links and missing resource requests. |
| **POST Request Scans** | `"(POST|PUT)\b` | Track state-changing API request paths. |
| **Bot Traffic** | `(?i)(bot|crawler|spider)` | Isolate web search spiders and automatic traffic. |
