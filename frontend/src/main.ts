// Chat client with feedback collection and insights view
import '../tailwind.css'

type Conversation = { id: number; title: string | null; created_at: string; updated_at: string }

type Feedback = {
  id: number
  conversation: number
  message: number
  is_helpful: boolean
  comment: string
  created_at: string
}

type Message = {
  id: number
  conversation: number
  role: 'user' | 'ai'
  text: string
  created_at: string
  sequence: number
  feedback?: Feedback | null
  tempId?: string
  pending?: boolean
}

type ConversationInsight = {
  conversation_id: number
  title: string | null
  feedback_count: number
  helpful_count: number
  not_helpful_count: number
  helpful_rate: number
  last_feedback_at: string
}

type RecentFeedback = {
  id: number
  conversation_id: number
  message_id: number
  title: string | null
  is_helpful: boolean
  comment: string
  created_at: string
  message_preview: string
}

type Insights = {
  total_feedback: number
  helpful_count: number
  not_helpful_count: number
  helpful_rate: number
  per_conversation: ConversationInsight[]
  recent_feedback: RecentFeedback[]
}

const root = document.getElementById('root')!

const state = {
  conversations: [] as Conversation[],
  current: null as Conversation | null,
  messages: [] as Message[],
  lastSeq: 0,
  pollTimer: 0 as any,
  feedbackDrafts: {} as Record<number, string>,
  feedbackSubmitting: {} as Record<number, boolean>,
  showInsights: false,
  insights: null as Insights | null,
  insightsLoading: false,
  insightsError: '',
}

async function api<T>(url: string, opts: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api/${url}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...opts,
  })
  const bodyText = await resp.text()
  if (!resp.ok) {
    throw new Error(bodyText || resp.statusText)
  }
  if (!bodyText.trim()) {
    return undefined as T
  }
  try {
    return JSON.parse(bodyText) as T
  } catch (err) {
    throw new Error(`Failed to parse JSON response: ${err}`)
  }
}

async function loadConversations() {
  const data = await api<{ results: Conversation[]; count: number }>('conversations/?limit=50')
  state.conversations = data.results
  if (!state.current && state.conversations.length) {
    state.current = state.conversations[0]
  }
  render()
}

async function createConversation(title?: string) {
  const data = await api<Conversation>('conversations/', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
  state.conversations.unshift(data)
  selectConversation(data.id)
}

async function deleteConversation(conversationId: number) {
  const convo = state.conversations.find((c) => c.id === conversationId)
  const label = convo?.title ? `"${convo.title}"` : 'this conversation'
  if (!window.confirm(`Delete ${label}? This cannot be undone.`)) return

  try {
    await api<void>(`conversations/${conversationId}/`, { method: 'DELETE' })
  } catch (err) {
    console.error(err)
    alert('Failed to delete conversation. Please try again.')
    return
  }

  state.conversations = state.conversations.filter((c) => c.id !== conversationId)
  const wasCurrent = state.current?.id === conversationId
  const next = state.conversations[0] ?? null

  if (wasCurrent) {
    state.current = null
    state.messages = []
    state.lastSeq = 0
    state.feedbackDrafts = {}
    state.feedbackSubmitting = {}
    if (next) {
      selectConversation(next.id)
    } else {
      render()
    }
  } else {
    render()
  }

  if (state.showInsights) {
    await loadInsights()
  }
}

function selectConversation(conversationId: number) {
  const convo = state.conversations.find((c) => c.id === conversationId) || null
  state.current = convo
  state.messages = []
  state.lastSeq = 0
  state.feedbackDrafts = {}
  state.feedbackSubmitting = {}
  state.showInsights = false
  render()
  loadMessages()
}

async function loadMessages() {
  if (!state.current) return
  const data = await api<{ results: Message[]; lastSeq: number }>(
    `conversations/${state.current.id}/messages/?since=${state.lastSeq}`
  )
  if (data.results.length) {
    state.messages.push(...data.results)
    state.lastSeq = data.lastSeq
    render()
    scrollChatToBottom()
  }
}

async function sendMessage(text: string) {
  if (!state.current) return
  const tempId = `tmp-${Date.now()}`
  const optimistic: Message = {
    id: -1,
    conversation: state.current.id,
    role: 'user',
    text,
    created_at: new Date().toISOString(),
    sequence: 0,
    tempId,
    pending: true,
  }
  state.messages.push(optimistic)
  render()
  scrollChatToBottom()

  try {
    const res = await api<{ user_message: Message; ai_message: Message }>(
      `conversations/${state.current.id}/messages/`,
      {
        method: 'POST',
        body: JSON.stringify({ text }),
      }
    )
    const idx = state.messages.findIndex((m) => m.tempId === tempId)
    if (idx >= 0) {
      state.messages.splice(idx, 1, res.user_message)
    } else {
      state.messages.push(res.user_message)
    }
    state.messages.push(res.ai_message)
    state.lastSeq = res.ai_message.sequence
    render()
    scrollChatToBottom()
  } catch (err) {
    const idx = state.messages.findIndex((m) => m.tempId === tempId)
    if (idx >= 0) state.messages.splice(idx, 1)
    render()
    alert('Failed to send message. Please try again.')
  }
}

async function submitFeedback(messageId: number, isHelpful: boolean) {
  if (!state.current) return
  const comment = (state.feedbackDrafts[messageId] ?? '').trim()
  state.feedbackSubmitting[messageId] = true
  render()

  try {
    const feedback = await api<Feedback>(
      `conversations/${state.current.id}/messages/${messageId}/feedback/`,
      {
        method: 'POST',
        body: JSON.stringify({ is_helpful: isHelpful, comment }),
      }
    )
    const msg = state.messages.find((m) => m.id === messageId)
    if (msg) {
      msg.feedback = feedback
    }
    state.feedbackDrafts[messageId] = feedback.comment ?? ''
    if (state.showInsights) {
      await loadInsights()
    } else {
      render()
    }
  } catch (err) {
    alert('Failed to submit feedback. Please try again.')
  } finally {
    delete state.feedbackSubmitting[messageId]
    if (!state.showInsights) {
      render()
    }
  }
}

async function loadInsights() {
  state.insightsLoading = true
  state.insightsError = ''
  render()
  try {
    const data = await api<Insights>('insights/')
    state.insights = data
  } catch (err) {
    state.insightsError = err instanceof Error ? err.message : String(err)
  } finally {
    state.insightsLoading = false
    render()
  }
}

function startPolling() {
  stopPolling()
  state.pollTimer = setInterval(loadMessages, 3000)
}
function stopPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer)
}

function ensureFeedbackDrafts() {
  state.messages.forEach((m) => {
    if (m.role === 'ai' && state.feedbackDrafts[m.id] === undefined) {
      state.feedbackDrafts[m.id] = m.feedback?.comment ?? ''
    }
  })
}

function scrollChatToBottom() {
  const c = document.getElementById('chat-scroll')
  if (c) c.scrollTop = c.scrollHeight
}

function render() {
  ensureFeedbackDrafts()
  root.innerHTML = `
  <div class="mx-auto max-w-5xl grid grid-cols-1 md:grid-cols-4 gap-4 p-4">
    <aside class="md:col-span-1 space-y-2">
      <div class="flex gap-2 items-center">
        <button id="new-conv" class="btn btn-primary flex-1">New Conversation</button>
      </div>
      <ul class="border rounded divide-y bg-white">
        ${state.conversations
          .map(
            (c) => `
          <li class="p-2 ${state.current?.id === c.id ? 'bg-blue-50' : ''}">
            <div class="flex items-start justify-between gap-2">
              <button data-cid="${c.id}" class="flex-1 text-left">
                ${escapeHtml(c.title ?? 'Untitled')}
                <br>
                <span class="text-xs text-gray-500">${new Date(c.updated_at).toLocaleString()}</span>
              </button>
              <button
                data-delete-cid="${c.id}"
                class="text-xs text-red-600 hover:text-red-800 focus:outline-none"
                title="Delete conversation"
                aria-label="Delete conversation"
              >
                Delete
              </button>
            </div>
          </li>
        `
          )
          .join('')}
      </ul>
    </aside>
    <main class="md:col-span-3 flex flex-col h-[80vh]">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h2 class="text-lg font-semibold">
            ${state.showInsights ? 'Feedback Insights' : escapeHtml(state.current?.title ?? 'Select a conversation')}
          </h2>
          ${
            !state.showInsights && state.current
              ? `<p class="text-xs text-gray-500">Updated ${new Date(state.current.updated_at).toLocaleString()}</p>`
              : ''
          }
        </div>
        <div class="flex gap-2">
          ${
            state.showInsights
              ? `<button id="refresh-insights" class="btn btn-secondary">Refresh</button>`
              : ''
          }
          <button id="toggle-insights" class="btn btn-secondary">
            ${state.showInsights ? 'Back to Chat' : 'View Insights'}
          </button>
        </div>
      </div>
      ${state.showInsights ? renderInsightsView() : renderChatView()}
    </main>
  </div>`

  document.getElementById('new-conv')?.addEventListener('click', () => {
    createConversation()
  })
  document.querySelectorAll('[data-cid]')?.forEach((el) => {
    el.addEventListener('click', () => {
      const cid = Number((el as HTMLElement).dataset.cid)
      selectConversation(cid)
    })
  })
  document.querySelectorAll('[data-delete-cid]')?.forEach((el) => {
    el.addEventListener('click', async (event) => {
      event.preventDefault()
      event.stopPropagation()
      const cid = Number((el as HTMLElement).dataset.deleteCid)
      if (!Number.isFinite(cid)) return
      await deleteConversation(cid)
    })
  })
  document.getElementById('toggle-insights')?.addEventListener('click', async () => {
    state.showInsights = !state.showInsights
    if (state.showInsights) {
      await loadInsights()
    } else {
      render()
      scrollChatToBottom()
    }
  })
  document.getElementById('refresh-insights')?.addEventListener('click', async () => {
    await loadInsights()
  })

  if (!state.showInsights) {
    const form = document.getElementById('composer') as HTMLFormElement | null
    form?.addEventListener('submit', async (e) => {
      e.preventDefault()
      const input = document.getElementById('input') as HTMLTextAreaElement
      const text = input.value.trim()
      if (!text) return
      if (text.length > 1000) {
        alert('Message too long')
        return
      }
      input.value = ''
      await sendMessage(text)
    })
  }

  document.querySelectorAll('[data-feedback-comment]')?.forEach((el) => {
    el.addEventListener('input', (event) => {
      const target = event.target as HTMLTextAreaElement
      const mid = Number(target.dataset.feedbackComment)
      state.feedbackDrafts[mid] = target.value
    })
  })
  document.querySelectorAll('[data-feedback]')?.forEach((el) => {
    el.addEventListener('click', async (event) => {
      const btn = event.currentTarget as HTMLButtonElement
      const mid = Number(btn.dataset.mid)
      const kind = btn.dataset.feedback
      if (state.feedbackSubmitting[mid]) return
      await submitFeedback(mid, kind === 'helpful')
    })
  })
}

function renderChatView(): string {
  if (!state.current) {
    return `
      <div class="flex-1 rounded border border-dashed border-gray-300 bg-white p-6 text-center text-gray-500 flex items-center justify-center">
        <p>Select a conversation or create a new one to begin chatting.</p>
      </div>
    `
  }

  return `
    <div id="chat-scroll" class="flex-1 overflow-auto border rounded bg-white p-3 space-y-3">
      ${
        state.messages.length
          ? state.messages.map(renderMessage).join('')
          : '<div class="text-center text-gray-500 py-12">No messages yet. Say hi!</div>'
      }
    </div>
    <form id="composer" class="mt-3 flex gap-2">
      <textarea id="input" class="textarea flex-1" rows="3" placeholder="Type a message (max 1000 chars)"></textarea>
      <button class="btn btn-primary" type="submit">Send</button>
    </form>
  `
}

function renderMessage(message: Message): string {
  const time = new Date(message.created_at).toLocaleTimeString()
  return `
    <div class="p-3 rounded ${message.role === 'user' ? 'msg-user' : 'msg-ai'} space-y-2">
      <div class="text-xs text-gray-500">${message.role.toUpperCase()} • ${time}</div>
      <div class="whitespace-pre-wrap">${escapeHtml(message.text)}</div>
      ${message.role === 'ai' ? renderFeedbackControls(message) : ''}
    </div>
  `
}

function renderFeedbackControls(message: Message): string {
  const submitting = !!state.feedbackSubmitting[message.id]
  const helpfulActive = message.feedback?.is_helpful === true
  const notHelpfulActive = message.feedback?.is_helpful === false
  const helpfulClass = helpfulActive
    ? 'bg-green-500 text-white border-green-500'
    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
  const notHelpfulClass = notHelpfulActive
    ? 'bg-red-500 text-white border-red-500'
    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
  const draft = state.feedbackDrafts[message.id] ?? ''
  const statusLine = message.feedback
    ? `<div class="text-xs text-gray-500">Marked ${
        message.feedback.is_helpful ? 'helpful' : 'not helpful'
      } • ${new Date(message.feedback.created_at).toLocaleString()}</div>`
    : ''
  return `
    <div class="mt-2 border-t pt-2 text-sm space-y-2">
      <div class="text-xs text-gray-500 uppercase tracking-wide">Was this helpful?</div>
      <div class="flex gap-2 flex-wrap">
        <button
          data-feedback="helpful"
          data-mid="${message.id}"
          class="px-3 py-1 rounded border text-sm transition ${helpfulClass}"
          ${submitting ? 'disabled' : ''}
        >
          Helpful
        </button>
        <button
          data-feedback="not"
          data-mid="${message.id}"
          class="px-3 py-1 rounded border text-sm transition ${notHelpfulClass}"
          ${submitting ? 'disabled' : ''}
        >
          Not Helpful
        </button>
      </div>
      <label class="block text-xs text-gray-500">Optional comment</label>
      <textarea
        data-feedback-comment="${message.id}"
        class="textarea textarea-sm w-full"
        rows="2"
        ${submitting ? 'disabled' : ''}
      >${escapeHtml(draft)}</textarea>
      ${statusLine}
    </div>
  `
}

function renderInsightsView(): string {
  if (state.insightsLoading) {
    return `
      <div class="flex-1 flex items-center justify-center border rounded bg-white p-6 text-gray-500">
        Loading insights...
      </div>
    `
  }

  if (state.insightsError) {
    return `
      <div class="flex-1 flex items-center justify-center border rounded bg-white p-6 text-red-600">
        Failed to load insights: ${escapeHtml(state.insightsError)}
      </div>
    `
  }

  if (!state.insights || state.insights.total_feedback === 0) {
    return `
      <div class="flex-1 flex items-center justify-center border rounded bg-white p-6 text-gray-500 text-center">
        No feedback submitted yet. Encourage users to rate AI responses to unlock insights.
      </div>
    `
  }

  const insights = state.insights
  const conversationRows = insights.per_conversation.length
    ? insights.per_conversation
        .map(
          (row) => `
        <tr class="border-b last:border-b-0">
          <td class="py-2">${escapeHtml(row.title ?? 'Untitled')}</td>
          <td class="py-2 text-center">${row.feedback_count}</td>
          <td class="py-2 text-center">${row.helpful_count}</td>
          <td class="py-2 text-center">${row.not_helpful_count}</td>
          <td class="py-2 text-center">${formatPercent(row.helpful_rate)}</td>
          <td class="py-2 text-right text-xs text-gray-500">${new Date(row.last_feedback_at).toLocaleString()}</td>
        </tr>
      `
        )
        .join('')
    : `<tr><td colspan="6" class="py-3 text-center text-gray-500">No conversation feedback yet.</td></tr>`

  const recentItems = insights.recent_feedback.length
    ? insights.recent_feedback
        .map(
          (item) => `
        <li class="border rounded p-3 bg-white shadow-sm">
          <div class="flex justify-between text-xs text-gray-500 mb-1">
            <span>${escapeHtml(item.title ?? 'Untitled conversation')}</span>
            <span>${new Date(item.created_at).toLocaleString()}</span>
          </div>
          <div class="${item.is_helpful ? 'text-green-600' : 'text-red-600'} font-semibold mb-1">
            ${item.is_helpful ? 'Helpful' : 'Not helpful'}
          </div>
          <div class="text-sm text-gray-700 mb-1">
            Response: ${escapeHtml(item.message_preview || '')}
          </div>
          ${
            item.comment
              ? `<div class="text-sm text-gray-600 italic">Comment: ${escapeHtml(item.comment)}</div>`
              : ''
          }
        </li>
      `
        )
        .join('')
    : '<li class="text-gray-500">No recent feedback.</li>'

  return `
    <div class="flex-1 overflow-auto space-y-6">
      <section class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="rounded border bg-white p-4">
          <div class="text-xs text-gray-500 uppercase">Total Feedback</div>
          <div class="text-2xl font-semibold">${insights.total_feedback}</div>
        </div>
        <div class="rounded border bg-white p-4">
          <div class="text-xs text-gray-500 uppercase">Helpful</div>
          <div class="text-2xl font-semibold text-green-600">${insights.helpful_count}</div>
        </div>
        <div class="rounded border bg-white p-4">
          <div class="text-xs text-gray-500 uppercase">Not Helpful</div>
          <div class="text-2xl font-semibold text-red-600">${insights.not_helpful_count}</div>
        </div>
        <div class="rounded border bg-white p-4">
          <div class="text-xs text-gray-500 uppercase">Helpful Rate</div>
          <div class="text-2xl font-semibold">${formatPercent(insights.helpful_rate)}</div>
        </div>
      </section>
      <section class="rounded border bg-white p-4">
        <h3 class="font-semibold mb-3">Top Conversations</h3>
        <div class="overflow-x-auto">
          <table class="w-full text-sm text-left">
            <thead class="text-xs uppercase text-gray-500 border-b">
              <tr>
                <th class="py-2">Conversation</th>
                <th class="py-2 text-center">Feedback</th>
                <th class="py-2 text-center">Helpful</th>
                <th class="py-2 text-center">Not Helpful</th>
                <th class="py-2 text-center">Helpful Rate</th>
                <th class="py-2 text-right">Last Feedback</th>
              </tr>
            </thead>
            <tbody>
              ${conversationRows}
            </tbody>
          </table>
        </div>
      </section>
      <section class="rounded border bg-white p-4">
        <h3 class="font-semibold mb-3">Recent Feedback</h3>
        <ul class="space-y-3">
          ${recentItems}
        </ul>
      </section>
    </div>
  `
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] as string))
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '0%'
  return `${Math.round(value * 100)}%`
}

// Boot
;(async function init() {
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = '/static/app/style.css'
  document.head.appendChild(link)
  await loadConversations()
  await loadMessages()
  startPolling()
})()
