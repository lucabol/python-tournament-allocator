# Skill: Inline Action Badges for User-Submitted Data

## Metadata
- **Category**: UI/UX Patterns
- **Confidence**: low
- **Source**: earned
- **Created**: 2026-02-16

## Context
When users submit data that requires organizer/admin review (e.g., scores, corrections, suggestions), displaying it as inline badges with single-click accept/dismiss actions provides better UX than modals or separate review queues.

## Pattern

### Visual Design
```html
<div class="pending-badge-container">
    <button class="pending-badge" onclick="acceptAction(this)">
        📩 [preview of submitted data]
    </button>
    <button class="pending-dismiss" onclick="dismissAction(this)">✕</button>
</div>
```

**CSS conventions:**
- Green badge for accept action (matches universal "confirm" color)
- Red dismiss button (matches universal "cancel" color)  
- Small size (font-size: 0.7rem, compact padding)
- Badge shows preview (e.g., "21-15" for scores, "3 items" for counts)
- Position: adjacent to the data item being reviewed

### Interaction Flow
1. **Accept**: Fills existing input fields with pending data, triggers normal save flow, dismisses pending state
2. **Dismiss**: Deletes pending record without applying, no confirmation needed (low risk)
3. **Multi-pending notification**: If 3+ items pending, show a banner at top ("⚠️ {count} items pending")

### Client-Side Rate Limiting (Optional)
```javascript
function isAlreadySubmitted(itemKey) {
    var key = 'pending_' + context;
    var submitted = JSON.parse(localStorage.getItem(key) || '[]');
    return submitted.indexOf(itemKey) !== -1;
}

function markAsSubmitted(itemKey) {
    var key = 'pending_' + context;
    var submitted = JSON.parse(localStorage.getItem(key) || '[]');
    if (submitted.indexOf(itemKey) === -1) {
        submitted.push(itemKey);
        localStorage.setItem(key, JSON.stringify(submitted));
    }
}
```

**Note**: This is UX-only rate limiting. Backend must enforce real rate limits.

## When to Use
✅ **Good fit:**
- Structured data submissions (scores, votes, edits)
- Low-friction review workflow (trust users, quick scanning)
- Inline context helps (seeing the badge next to the match/item)

❌ **Not recommended:**
- Unstructured text (comments, messages) — use modals or dedicated views
- High-risk actions (financial, legal) — need stronger confirmation
- Complex multi-field edits — badge can't show sufficient preview

## Anti-Patterns
- Don't use modals for accept/dismiss — adds unnecessary friction
- Don't require confirmation for dismiss — it's a low-risk action
- Don't show full data in badge — use compact preview (score, count, truncated text)
- Don't create parallel save logic — reuse existing save endpoints

## Examples
- **Match score reporting**: Badge shows "📩 21-15", click fills score inputs and auto-saves
- **Schedule change requests**: Badge shows "📩 Move to Court 2", click applies change
- **Team name corrections**: Badge shows "📩 Team A → Team Alpha", click renames

## Related Patterns
- Notification badges (numeric counts, not actionable)
- Inline editing (direct field manipulation, no pending state)
- Review queues (separate page, batch operations)
