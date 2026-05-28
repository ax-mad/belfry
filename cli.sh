#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# 🔔 Belfry CLI — Interactive reminder management powered by gum
# =============================================================================

BELFRY_URL="${BELFRY_URL:-http://localhost:8000}"

# ─── Dracula Color Palette ────────────────────────────────────────────────────
PINK="#FF79C6"
CYAN="#8BE9FD"
GREEN="#50FA7B"
YELLOW="#F1FA8C"
PURPLE="#BD93F9"
RED="#FF5555"
FG="#F8F8F2"
COMMENT="#6272A4"

# ─── Header ───────────────────────────────────────────────────────────────────
gum style \
  --border double \
  --margin "1" \
  --padding "1 4" \
  --align center \
  --foreground "$PINK" \
  "🔔 Belfry CLI" \
  "" \
  "$(gum style --foreground "$CYAN" "Reminder management for the belfry")"

# ─── Dependency Check ─────────────────────────────────────────────────────────
for cmd in gum curl jq; do
  if ! command -v "$cmd" &>/dev/null; then
    gum style --foreground "$RED" "ERROR: '$cmd' is not installed."
    exit 1
  fi
done

# ─── Helpers ──────────────────────────────────────────────────────────────────

_api() {
  local method="$1" path="$2" data="${3:-}"
  if [ -n "$data" ]; then
    curl -s -X "$method" "${BELFRY_URL}${path}" \
      -H "Content-Type: application/json" \
      -d "$data"
  else
    curl -s -X "$method" "${BELFRY_URL}${path}"
  fi
}

_confirm() {
  gum confirm --affirmative "Yes" --negative "No" "$1"
}

# ─── Create Reminder ─────────────────────────────────────────────────────────

create_reminder() {
  gum style --foreground "$CYAN" --margin "1 0" "📝 Create a new reminder"

  # ── Reminder ID ──────────────────────────────────────────────────────────
  local reminder_id
  reminder_id=$(gum input --placeholder "reminder-id" --prompt "$(gum style --foreground "$GREEN" "➜ ID: ")")
  [ -z "$reminder_id" ] && { gum style --foreground "$RED" "ID is required"; return; }

  # ── Schedule (REQUIRED) ─────────────────────────────────────────────────
  local schedule
  gum style --foreground "$COMMENT" "Schedule: cron expression (5-field) or natural language"
  schedule=$(gum input --placeholder "* * * * *" --prompt "$(gum style --foreground "$GREEN" "➜ Schedule: ")")
  [ -z "$schedule" ] && { gum style --foreground "$RED" "Schedule is required"; return; }

  # ── Message (REQUIRED) ──────────────────────────────────────────────────
  local message
  message=$(gum write --placeholder "Enter reminder message..." --height 4)
  [ -z "$message" ] && { gum style --foreground "$RED" "Message is required"; return; }

  # ── Build payload ──────────────────────────────────────────────────────────
  local json_payload
  json_payload=$(jq -n \
    --arg msg "$message" \
    '{message: $msg}')

  # ── Optional fields selection ────────────────────────────────────────────
  gum style --foreground "$COMMENT" --margin "1 0" "Select optional fields to fill:"

  local selected
  selected=$(gum choose --no-limit \
    "title" \
    "priority" \
    "tags" \
    "attach" \
    "actions" \
    --header "$(gum style --foreground "$FG" "Space to select, Enter to confirm")")

  # ── Title ─────────────────────────────────────────────────────────────────
  if echo "$selected" | grep -q "title"; then
    local title
    title=$(gum input --placeholder "Notification title" --prompt "$(gum style --foreground "$GREEN" "➜ Title: ")")
    [ -n "$title" ] && json_payload=$(echo "$json_payload" | jq --arg t "$title" '.title = $t')
  fi

  # ── Priority ──────────────────────────────────────────────────────────────
  if echo "$selected" | grep -q "priority"; then
    local priority
    priority=$(gum input --placeholder "1-5 (default: 3)" --prompt "$(gum style --foreground "$GREEN" "➜ Priority: ")")
    [ -n "$priority" ] && json_payload=$(echo "$json_payload" | jq --argjson p "${priority:-3}" '.priority = $p')
  fi

  # ── Tags ──────────────────────────────────────────────────────────────────
  if echo "$selected" | grep -q "tags"; then
    local tags_input tags_json
    tags_input=$(gum input --placeholder "tag1, tag2, tag3" --prompt "$(gum style --foreground "$GREEN" "➜ Tags: ")")
    if [ -n "$tags_input" ]; then
      tags_json=$(echo "$tags_input" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | jq -R . | jq -s .)
      json_payload=$(echo "$json_payload" | jq --argjson t "$tags_json" '.tags = $t')
    fi
  fi

  # ── Attach ────────────────────────────────────────────────────────────────
  if echo "$selected" | grep -q "attach"; then
    local attach
    attach=$(gum input --placeholder "https://example.com/image.jpg" --prompt "$(gum style --foreground "$GREEN" "➜ Attach URL: ")")
    [ -n "$attach" ] && json_payload=$(echo "$json_payload" | jq --arg a "$attach" '.attach = $a')
  fi

  # ── Actions ───────────────────────────────────────────────────────────────
  if echo "$selected" | grep -q "actions"; then
    local actions_json="[]"
    while true; do
      gum style --foreground "$YELLOW" "Adding action..."
      local action_type label action_url action_obj

      action_type=$(gum choose \
        "view" \
        "broadcast" \
        "http" \
        "copy" \
        --header "$(gum style --foreground "$FG" "Action type")")

      label=$(gum input --placeholder "Button label" --prompt "$(gum style --foreground "$GREEN" "➜ Label: ")")
      [ -z "$label" ] && break

      action_obj=$(jq -n \
        --arg action "$action_type" \
        --arg label "$label" \
        '{action: $action, label: $label}')

      case "$action_type" in
        view|http)
          action_url=$(gum input --placeholder "https://..." --prompt "$(gum style --foreground "$GREEN" "➜ URL: ")")
          [ -n "$action_url" ] && action_obj=$(echo "$action_obj" | jq --arg u "$action_url" '.url = $u')
          ;;
        copy)
          local copy_value
          copy_value=$(gum input --placeholder "Text to copy" --prompt "$(gum style --foreground "$GREEN" "➜ Value: ")")
          [ -n "$copy_value" ] && action_obj=$(echo "$action_obj" | jq --arg v "$copy_value" '.value = $v')
          ;;
      esac

      # Optional:  flag
      if gum confirm --affirmative "Yes" --negative "No" "Dismiss notification on tap?"; then
        action_obj=$(echo "$action_obj" | jq '. = true')
      fi

      actions_json=$(echo "$actions_json" | jq --argjson a "$action_obj" '. + [$a]')

      gum confirm --affirmative "Add another" --negative "Done" "Add another action?" || break
    done

    [ "$(echo "$actions_json" | jq length)" -gt 0 ] && \
      json_payload=$(echo "$json_payload" | jq --argjson a "$actions_json" '.actions = $a')
  fi

  # ── Build final request ──────────────────────────────────────────────────
  local request_body
  request_body=$(jq -n \
    --arg schedule "$schedule" \
    --argjson payload "$json_payload" \
    '{schedule: $schedule, payload: $payload}')

  # ── Preview & Confirm ────────────────────────────────────────────────────
  gum style --foreground "$CYAN" --margin "1 0" "📋 Preview:"
  echo "$request_body" | jq . | gum style --foreground "$FG" --border normal --padding "1 2"

  _confirm "Send this reminder to the belfry?" || { gum style --foreground "$COMMENT" "Cancelled."; return; }

  # ── Send ─────────────────────────────────────────────────────────────────
  local resp
  resp=$(_api "POST" "/reminders/${reminder_id}" "$request_body")

  if echo "$resp" | jq -e '.status' &>/dev/null; then
    gum style --foreground "$GREEN" --margin "1" "✅ Reminder '${reminder_id}' scheduled!"
  else
    gum style --foreground "$RED" --margin "1" "❌ Failed: $(echo "$resp" | jq -r '.detail // . // empty')"
  fi
}

# ─── List Reminders ──────────────────────────────────────────────────────────
list_reminders() {
  gum style --foreground "$CYAN" --margin "1 0" "📋 Reminders in the belfry"
  # This would need a GET endpoint; for now, show a placeholder
  gum style --foreground "$COMMENT" "(Implement GET /reminders in belfry API to list all)"
}

# ─── Pause Reminder ──────────────────────────────────────────────────────────
pause_reminder() {
  gum style --foreground "$CYAN" --margin "1 0" "⏸️  Pause a reminder"
  local id
  id=$(gum input --placeholder "reminder-id" --prompt "$(gum style --foreground "$GREEN" "➜ ID: ")")
  [ -z "$id" ] && return

  _confirm "Pause reminder '${id}'?" || return

  local resp
  resp=$(_api "PUT" "/reminders/${id}/")

  if echo "$resp" | jq -e '.status' &>/dev/null; then
    gum style --foreground "$YELLOW" "⏸️  Reminder '${id}' paused."
  else
    gum style --foreground "$RED" "❌ Failed: $(echo "$resp" | jq -r '.detail // empty')"
  fi
}

# ─── Delete Reminder ─────────────────────────────────────────────────────────
delete_reminder() {
  gum style --foreground "$CYAN" --margin "1 0" "🗑️  Delete a reminder"
  local id
  id=$(gum input --placeholder "reminder-id" --prompt "$(gum style --foreground "$GREEN" "➜ ID: ")")
  [ -z "$id" ] && return

  gum style --foreground "$RED" "⚠️  This cannot be undone!"
  _confirm "Delete reminder '${id}'?" || return

  local resp
  resp=$(_api "DELETE" "/reminders/${id}")

  if echo "$resp" | jq -e '.status' &>/dev/null; then
    gum style --foreground "$GREEN" "🗑️  Reminder '${id}' deleted."
  else
    gum style --foreground "$RED" "❌ Failed: $(echo "$resp" | jq -r '.detail // empty')"
  fi
}

# ─── Main Menu ─────────────────────────────────────────────────────────────
main_menu() {
  while true; do
    local choice
    choice=$(gum choose \
      "📝 Create reminder" \
      "⏸️  Pause reminder" \
      "🗑️  Delete reminder" \
      "❌ Exit" \
      --header "$(gum style --foreground "$FG" "What would you like to do?")")

    case "$choice" in
      "📝 Create reminder") create_reminder ;;
      "⏸️  Pause reminder") pause_reminder ;;
      "🗑️  Delete reminder") delete_reminder ;;
      "❌ Exit") gum style --foreground "$COMMENT" "Goodbye."; exit 0 ;;
    esac

    echo
    gum style --foreground "$COMMENT" "Press Enter to continue..."
    read -r
        gum style \
      --border double \
      --margin "1" \
      --padding "1 4" \
      --align center \
      --foreground "$PINK" \
      "🔔 Belfry CLI"
  done
}

main_menu
