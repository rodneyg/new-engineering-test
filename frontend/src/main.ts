// Minimal client: conversations list, chat view, polling
import '../tailwind.css'

type Conversation = { id: number; title: string | null; created_at: string; updated_at: string }
type Message = {
  id: number
  conversation: number
  role: 'user' | 'ai'
  text: string
  created_at: string
  sequence: number
  tempId?: string
  pending?: boolean
}

const root = document.getElementById('root')!

const state = {
  conversations: [] as Conversation[],
  current: null as Conversation | null,
  messages: [] as Message[],
  lastSeq: 0,
  pollTimer: 0 as any,
}

async function api<T>(url: string, opts: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api/${url}`, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...opts,
  })
  if (!resp.ok) throw new Error(await resp.text())
  return resp.json()
}

async function loadConversations() {
  const data = await api<{ results: Conversation[]; count: number }>(`conversations/?limit=50`)
  state.conversations = data.results
  if (!state.current && state.conversations.length) state.current = state.conversations[0]
  render()
}

async function createConversation(title?: string) {
  const data = await api<Conversation>('conversations/', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
  state.conversations.unshift(data)
  state.current = data
  state.messages = []
  state.lastSeq = 0
  render()
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

function startPolling() {
  stopPolling()
  state.pollTimer = setInterval(loadMessages, 3000)
}
function stopPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer)
}

function scrollChatToBottom() {
  const c = document.getElementById('chat-scroll')
  if (c) c.scrollTop = c.scrollHeight
}

function render() {
  root.innerHTML = `
  <div class="mx-auto max-w-5xl grid grid-cols-1 md:grid-cols-4 gap-4 p-4">
    <aside class="md:col-span-1 space-y-2">
      <div class="flex gap-2 items-center">
        <button id="new-conv" class="btn btn-primary">New Conversation</button>
      </div>
      <ul class="border rounded divide-y bg-white">
        ${state.conversations
          .map(
            (c) => `
          <li class="p-2 ${state.current?.id === c.id ? 'bg-blue-50' : ''}">
            <button data-cid="${c.id}" class="w-full text-left">${c.title ?? 'Untitled'}<br><span class="text-xs text-gray-500">${new Date(c.updated_at).toLocaleString()}</span></button>
          </li>
        `
          )
          .join('')}
      </ul>
    </aside>
    <main class="md:col-span-3 flex flex-col h-[80vh]">
      <div id="chat-scroll" class="flex-1 overflow-auto border rounded bg-white p-3 space-y-3">
        ${state.messages
          .map(
            (m) => `
          <div class="p-3 rounded ${m.role === 'user' ? 'msg-user' : 'msg-ai'}">
            <div class="text-xs text-gray-500 mb-1">${m.role.toUpperCase()} • ${new Date(m.created_at).toLocaleTimeString()}</div>
            <div class="whitespace-pre-wrap">${escapeHtml(m.text)}</div>
          </div>
        `
          )
          .join('')}
      </div>
      <form id="composer" class="mt-3 flex gap-2">
        <textarea id="input" class="textarea flex-1" rows="3" placeholder="Type a message (max 1000 chars)"></textarea>
        <button class="btn btn-primary" type="submit">Send</button>
      </form>
    </main>
  </div>`

  document.getElementById('new-conv')?.addEventListener('click', () => {
    createConversation()
  })
  document.querySelectorAll('[data-cid]')?.forEach((el) => {
    el.addEventListener('click', () => {
      const cid = Number((el as HTMLElement).dataset.cid)
      const c = state.conversations.find((x) => x.id === cid) || null
      state.current = c
      state.messages = []
      state.lastSeq = 0
      render()
      loadMessages()
    })
  })
  const form = document.getElementById('composer') as HTMLFormElement
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

function escapeHtml(s: string) {
  return s.replace(
    /[&<>"]/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string
  )
}

// Boot
;(async function init() {
  // Inject Tailwind (built via PostCSS)
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = '/static/app/style.css'
  document.head.appendChild(link)
  await loadConversations()
  await loadMessages()
  startPolling()
})()
