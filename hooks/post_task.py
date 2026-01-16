#!/usr/bin/env python3
"""
PostToolUse Hook for Task tool
自動呼叫 finish_task() / finish_validation()

設計原則：
1. Hook 職責最小化 - 只做「標記完成 + 推進 phase」
2. Executor 一律視為成功 - 品質判斷由 Critic 負責
3. Critic 判斷結果 - 解析 APPROVED / CONDITIONAL / REJECTED 關鍵字
"""
import json
import sys
import os
import re
from datetime import datetime

# 動態計算路徑（相對於此模組位置）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE_DIR)

LOG_PATH = os.path.join(_BASE_DIR, 'hooks', 'hook.log')


def log(msg: str):
    """寫入 debug log"""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except:
        pass  # 忽略 log 錯誤


# ========== Main ==========

# 讀取 stdin JSON
try:
    input_data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)

# 只處理 Task tool
tool_name = input_data.get("tool_name", "")
if tool_name != "Task":
    sys.exit(0)

tool_input = input_data.get("tool_input", {})
tool_response = input_data.get("tool_response", {})

prompt = tool_input.get("prompt", "")
subagent_type = tool_input.get("subagent_type", "")

# 解析 TASK_ID
task_match = re.search(r'TASK_ID\s*=\s*["\']([^"\']+)["\']', prompt)
if not task_match:
    log(f"No TASK_ID found in prompt for {subagent_type}")
    sys.exit(0)

task_id = task_match.group(1)

# agent_id 可能在 dict 或解析失敗時為 None
if isinstance(tool_response, dict):
    agent_id = tool_response.get("agentId")
else:
    agent_id = None

log(f"[{subagent_type}] task_id={task_id}, agent_id={agent_id}")

try:
    from servers.tasks import update_task, get_task
    from servers.facade import finish_task, finish_validation

    # === Executor 處理 ===
    if subagent_type == "executor":
        # 記錄 agentId（用於 resume）
        if agent_id:
            update_task(task_id, executor_agent_id=agent_id)
            log(f"Recorded agentId {agent_id} for task {task_id}")

        # 一律視為成功，推進到 validation
        # 真正的品質判斷由 Critic 負責
        result = finish_task(task_id, success=True, result="Executor completed")
        log(f"finish_task result: {result}")

    # === Critic 處理 ===
    elif subagent_type == "critic":
        # 解析 ORIGINAL_TASK_ID
        orig_match = re.search(r'ORIGINAL_TASK_ID\s*=\s*["\']([^"\']+)["\']', prompt)
        if not orig_match:
            log(f"ERROR: ORIGINAL_TASK_ID not found in prompt")
            sys.exit(0)

        original_task_id = orig_match.group(1)

        # 解析 Critic 輸出中的判斷結果
        # 支援三種: APPROVED / CONDITIONAL / REJECTED
        # 使用正則表達式精確匹配「驗證結果:」後的關鍵字
        response_text = str(tool_response)

        # 精確匹配格式: "驗證結果: APPROVED" 或 "驗證結果: REJECTED" 等
        verdict_match = re.search(r'驗證結果\s*[:：]\s*(APPROVED|CONDITIONAL|REJECTED)', response_text, re.IGNORECASE)

        if verdict_match:
            verdict = verdict_match.group(1).upper()
        else:
            # 備用：檢查是否有獨立的關鍵字行（如 "## APPROVED"）
            if re.search(r'^#+\s*REJECTED\s*$', response_text, re.MULTILINE | re.IGNORECASE):
                verdict = "REJECTED"
            elif re.search(r'^#+\s*CONDITIONAL\s*$', response_text, re.MULTILINE | re.IGNORECASE):
                verdict = "CONDITIONAL"
            elif re.search(r'^#+\s*APPROVED\s*$', response_text, re.MULTILINE | re.IGNORECASE):
                verdict = "APPROVED"
            else:
                # 預設通過
                verdict = "APPROVED"

        if verdict == "REJECTED":
            approved = False
            conditional = False
            log(f"Critic verdict: REJECTED for task {original_task_id}")
        elif verdict == "CONDITIONAL":
            approved = True  # CONDITIONAL 視為通過
            conditional = True
            log(f"Critic verdict: CONDITIONAL for task {original_task_id}")
            # 將建議存入 working_memory 供主對話參考
            try:
                from servers.memory import set_working_memory
                set_working_memory(original_task_id, 'critic_suggestions', response_text)
                log(f"Saved critic_suggestions to working_memory")
            except Exception as e:
                log(f"Failed to save critic_suggestions: {e}")
        else:
            # APPROVED
            approved = True
            conditional = False
            log(f"Critic verdict: APPROVED for task {original_task_id}")

        # 呼叫 finish_validation
        result = finish_validation(task_id, original_task_id, approved=approved)
        log(f"finish_validation result: {result}")

        # 如果是 CONDITIONAL，輸出提醒給主對話
        if conditional:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"任務 {original_task_id} 有條件通過。建議存於 working_memory['critic_suggestions']。"
                }
            }
            print(json.dumps(output))

except Exception as e:
    log(f"ERROR: {str(e)}")
    import traceback
    log(traceback.format_exc())

sys.exit(0)
