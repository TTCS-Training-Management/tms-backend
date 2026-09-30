import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type Role = 'admin' | 'lecturer' | 'accountant'
type User = { id: number; full_name: string; email: string; role: Role; is_active: boolean; created_at: string }
type Summary = { greeting: string; total_users: number; active_users: number; locked_users: number }

const API_URL = 'http://127.0.0.1:8000'
const roleLabels: Record<Role, string> = { admin: 'Quản trị viên', lecturer: 'Giảng viên', accountant: 'Kế toán' }

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('tms_token')
  const response = await fetch(`${API_URL}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Có lỗi xảy ra' }))
    if (response.status === 401 || response.status === 403) {
      const message = error.detail ?? 'Bạn không có quyền truy cập chức năng này'
      window.dispatchEvent(new CustomEvent('tms:notice', { detail: message }))
      if (response.status === 401) window.dispatchEvent(new CustomEvent('tms:session-expired', { detail: 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.' }))
    }
    throw new Error(error.detail ?? 'Có lỗi xảy ra')
  }
  return response.json() as Promise<T>
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loginError, setLoginError] = useState('')
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<'overview' | 'users'>('overview')
  const [summary, setSummary] = useState<Summary | null>(null)
  const [users, setUsers] = useState<User[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [notice, setNotice] = useState('')
  const [appError, setAppError] = useState<{ title: string; message: string; actionLabel: string } | null>(null)

  useEffect(() => {
    if (!localStorage.getItem('tms_token')) { setLoading(false); return }
    apiRequest<User>('/auth/me').then(setUser).catch(() => localStorage.removeItem('tms_token')).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!user) return
    apiRequest<Summary>('/dashboard/summary').then(setSummary).catch(() => undefined)
    if (user.role === 'admin') apiRequest<User[]>('/users').then(setUsers).catch(() => undefined)
  }, [user])

  useEffect(() => {
    const showNotice = (event: Event) => setNotice((event as CustomEvent<string>).detail)
    window.addEventListener('tms:notice', showNotice)
    return () => window.removeEventListener('tms:notice', showNotice)
  }, [])

  useEffect(() => {
    const expireSession = (event: Event) => {
      const detail = (event as CustomEvent<string>).detail
      localStorage.removeItem('tms_token')
      setUser(null)
      setSummary(null)
      setUsers([])
      setAppError({ title: 'Phiên đăng nhập đã hết hạn', message: detail, actionLabel: 'Đăng nhập lại' })
      setLoginError(detail)
    }
    window.addEventListener('tms:session-expired', expireSession)
    return () => window.removeEventListener('tms:session-expired', expireSession)
  }, [])

  useEffect(() => {
    if (!user) return
    const refreshTimer = window.setInterval(async () => {
      try {
        const result = await apiRequest<{ access_token: string }>('/auth/refresh', { method: 'POST' })
        localStorage.setItem('tms_token', result.access_token)
      } catch {
        // The session-expired event handles the redirect to login.
      }
    }, 5 * 60 * 1000)
    return () => window.clearInterval(refreshTimer)
  }, [user])

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoginError('')
    const data = new FormData(event.currentTarget)
    try {
      const result = await apiRequest<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify({ email: data.get('email'), password: data.get('password') }) })
      localStorage.setItem('tms_token', result.access_token); localStorage.removeItem('tms_login_email'); setUser(result.user)
    } catch (error) { setLoginError(error instanceof Error ? error.message : 'Không thể đăng nhập') }
  }

  async function logout() { await apiRequest('/auth/logout', { method: 'POST' }).catch(() => undefined); localStorage.removeItem('tms_token'); setUser(null); setSummary(null) }
  async function toggleStatus(id: number) { const updated = await apiRequest<User>(`/users/${id}/status`, { method: 'PATCH' }); setUsers((current) => current.map((item) => item.id === id ? updated : item)) }
  async function changeRole(id: number, role: Role) { const updated = await apiRequest<User>(`/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }); setUsers((current) => current.map((item) => item.id === id ? updated : item)) }
  async function createUser(data: { full_name: string; email: string; password: string; role: Role }) { const created = await apiRequest<User>('/users', { method: 'POST', body: JSON.stringify(data) }); setUsers((current) => [created, ...current]); setCreateOpen(false) }
  async function editUser(id: number, data: { full_name: string; email: string }) { const updated = await apiRequest<User>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }); setUsers((current) => current.map((item) => item.id === id ? updated : item)) }
  async function changePassword(data: { current_password: string; new_password: string }) { await apiRequest('/auth/change-password', { method: 'POST', body: JSON.stringify(data) }); setPasswordOpen(false) }

  if (loading) return <div className="page-loader">Đang khởi động hệ thống...</div>
  if (appError) return <ErrorScreen title={appError.title} message={appError.message} actionLabel={appError.actionLabel} onAction={() => { setAppError(null); setUser(null); setLoginError(''); setNotice(''); }} />
  if (!user) return <LoginPage error={loginError} onSubmit={login} />
  return <div className="app-shell">{notice && <div className="notice" role="alert">{notice}<button onClick={() => setNotice('')} aria-label="Đóng thông báo">×</button></div>}<aside className="sidebar"><div className="brand"><div className="brand-mark">T</div><div><strong>TMS</strong><span>Training Management</span></div></div><div className="workspace-label">KHÔNG GIAN LÀM VIỆC</div><nav className="main-nav"><button className={view === 'overview' ? 'nav-item active' : 'nav-item'} onClick={() => setView('overview')}><span>⌂</span>Tổng quan</button>{user.role === 'admin' && <button className={view === 'users' ? 'nav-item active' : 'nav-item'} onClick={() => setView('users')}><span>♙</span>Tài khoản</button>}</nav><div className="sidebar-bottom"><button className="profile-mini" onClick={logout}><Avatar name={user.full_name} /><span><strong>{user.full_name}</strong><small>{roleLabels[user.role]}</small></span><span className="logout-icon">↪</span></button></div></aside><main className="main-content"><header className="topbar"><div className="breadcrumb">Hệ thống / <strong>{view === 'overview' ? 'Tổng quan' : 'Tài khoản'}</strong></div><div className="topbar-actions"><span className="status-dot" />Hệ thống đang hoạt động<button className="icon-button" onClick={() => setPasswordOpen(true)} aria-label="Đổi mật khẩu">⌘</button></div></header><div className="content-wrap">{view === 'overview' ? <Overview user={user} summary={summary} onUsers={() => setView('users')} /> : <UsersView users={users} onCreate={() => setCreateOpen(true)} onToggle={toggleStatus} onRoleChange={changeRole} onEdit={editUser} />}</div></main>{createOpen && <CreateUserModal onClose={() => setCreateOpen(false)} onCreate={createUser} />}{passwordOpen && <ChangePasswordModal onClose={() => setPasswordOpen(false)} onChange={changePassword} />}</div>
}

function ErrorScreen({ title, message, actionLabel, onAction }: { title: string; message: string; actionLabel: string; onAction: () => void }) {
  return <main className="error-screen"><div className="error-card"><div className="brand-mark large">T</div><p className="eyebrow blue">THÔNG BÁO</p><h2>{title}</h2><p>{message}</p><button className="primary-button full" onClick={onAction}>{actionLabel}</button></div></main>
}

function LoginPage({ error, onSubmit }: { error: string; onSubmit: (event: FormEvent<HTMLFormElement>) => void }) {
  const [forgot, setForgot] = useState(false)
  const [forgotMessage, setForgotMessage] = useState('')
  const [resetRequested, setResetRequested] = useState(false)
  const [resetToken, setResetToken] = useState('')
  const [newPassword, setNewPassword] = useState('')

  async function requestReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get('email'));
    try {
      const result = await apiRequest<{ message: string }>('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
      setResetRequested(true)
      setForgotMessage(result.message)
    } catch (requestError) {
      setResetRequested(false)
      setForgotMessage(requestError instanceof Error ? requestError.message : 'Không thể khôi phục mật khẩu')
    }
  }

  async function submitReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const result = await apiRequest<{ message: string }>('/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token: resetToken, new_password: newPassword }),
      })
      setForgotMessage(result.message)
      setResetRequested(false)
      setResetToken('')
      setNewPassword('')
      setForgot(false)
    } catch (requestError) {
      setForgotMessage(requestError instanceof Error ? requestError.message : 'Không thể đặt lại mật khẩu')
    }
  }

  return <main className="login-page"><section className="login-visual"><div className="visual-overlay" /></section><section className="login-panel"><div className="login-form-wrap login-card"><div className="school-brand"><div className="brand-mark">T</div><h1>HỆ THỐNG ĐÀO TẠO TRỰC TUYẾN</h1></div>{forgot ? <><p className="eyebrow blue">KHÔI PHỤC TRUY CẬP</p><h2>Quên mật khẩu</h2><p className="form-intro">Nhập email để nhận mã khôi phục và đặt lại mật khẩu mới.</p><form onSubmit={requestReset} className="login-form"><label>Email công việc<input name="email" type="email" defaultValue={localStorage.getItem('tms_login_email') ?? ''} onChange={(event) => localStorage.setItem('tms_login_email', event.target.value)} required /></label><button className="primary-button full" type="submit">Tạo mã khôi phục</button></form>{forgotMessage && <div className={forgotMessage.toLowerCase().includes('thành công') ? 'form-success' : 'form-error'}>{forgotMessage}</div>}{resetRequested && <form onSubmit={submitReset} className="login-form"><label>Mã khôi phục<input value={resetToken} onChange={(event) => setResetToken(event.target.value)} required /></label><label>Mật khẩu mới<input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} minLength={8} placeholder="Ít nhất 8 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt" required /></label><button className="primary-button full" type="submit">Đặt lại mật khẩu</button></form>}<button className="link-button back-link" onClick={() => { setForgot(false); setForgotMessage(''); setResetRequested(false); setResetToken(''); setNewPassword('') }}>← Quay lại đăng nhập</button></> : <><p className="eyebrow blue">CHÀO MỪNG QUAY TRỞ LẠI</p><h2>Đăng nhập</h2><p className="form-intro">Đăng nhập để tiếp tục với không gian làm việc của bạn.</p><form onSubmit={onSubmit} className="login-form"><label>Email công việc<input name="email" type="email" defaultValue={localStorage.getItem('tms_login_email') ?? ''} onChange={(event) => localStorage.setItem('tms_login_email', event.target.value)} required /></label><label>Mật khẩu<input name="password" type="password" required /></label>{error && <div className="form-error">{error}</div>}<button className="primary-button full" type="submit">Đăng nhập <span>→</span></button></form><button className="link-button back-link" onClick={() => setForgot(true)}>Quên mật khẩu?</button></>}</div></section></main>
}

function Overview({ user, summary, onUsers }: { user: User; summary: Summary | null; onUsers: () => void }) {
  return <div className="view"><div className="page-heading"><div><p className="eyebrow blue">TỔNG QUAN HỆ THỐNG</p><h1>Chào buổi sáng, {user.full_name.split(' ').at(-1)}</h1><p className="muted">Theo dõi nhanh trạng thái tài khoản và quyền truy cập.</p></div><button className="primary-button" onClick={onUsers}>Quản lý tài khoản <span>→</span></button></div><div className="stat-grid"><StatCard label="Tổng tài khoản" value={summary?.total_users ?? '—'} detail="Trong hệ thống" icon="◎" tone="blue" /><StatCard label="Đang hoạt động" value={summary?.active_users ?? '—'} detail="Tài khoản khả dụng" icon="✓" tone="green" /><StatCard label="Đang bị khóa" value={summary?.locked_users ?? '—'} detail="Cần kiểm tra" icon="⊘" tone="orange" /></div></div>
}
function StatCard({ label, value, detail, icon, tone }: { label: string; value: string | number; detail: string; icon: string; tone: string }) { return <article className="stat-card"><div className={`stat-icon ${tone}`}>{icon}</div><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div><span className="stat-arrow">↗</span></article> }
function Avatar({ name }: { name: string }) { return <span className="avatar">{name.split(' ').map((part) => part[0]).slice(-2).join('').toUpperCase()}</span> }

function UsersView({ users, onCreate, onToggle, onRoleChange, onEdit }: { users: User[]; onCreate: () => void; onToggle: (id: number) => Promise<void>; onRoleChange: (id: number, role: Role) => Promise<void>; onEdit: (id: number, data: { full_name: string; email: string }) => Promise<void> }) {
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState<User | null>(null)
  const filteredUsers = users.filter((item) => `${item.full_name} ${item.email}`.toLowerCase().includes(query.toLowerCase()))
  return <div className="view"><div className="page-heading"><div><p className="eyebrow blue">QUẢN TRỊ HỆ THỐNG</p><h1>Tài khoản</h1><p className="muted">Quản lý thành viên và quyền truy cập vào hệ thống.</p></div><button className="primary-button" onClick={onCreate}>＋ Tạo tài khoản</button></div><section className="table-card"><div className="table-toolbar"><div className="search-box">⌕<input placeholder="Tìm theo tên hoặc email" value={query} onChange={(event) => setQuery(event.target.value)} /></div><span className="table-count">{filteredUsers.length} tài khoản</span></div><div className="table-scroll"><table><thead><tr><th>Người dùng</th><th>Vai trò</th><th>Trạng thái</th><th>Ngày tạo</th><th /></tr></thead><tbody>{filteredUsers.map((item) => <tr key={item.id}><td><div className="user-cell"><Avatar name={item.full_name} /><span><strong>{item.full_name}</strong><small>{item.email}</small></span></div></td><td><select className="role-select" value={item.role} onChange={(event) => onRoleChange(item.id, event.target.value as Role)}><option value="admin">Quản trị viên</option><option value="lecturer">Giảng viên</option><option value="accountant">Kế toán</option></select></td><td><span className={item.is_active ? 'status-pill active' : 'status-pill locked'}><i />{item.is_active ? 'Hoạt động' : 'Đã khóa'}</span></td><td className="date-cell">{new Date(item.created_at).toLocaleDateString('vi-VN')}</td><td><button className="row-action" onClick={() => setEditing(item)}>Sửa</button><button className={item.is_active ? 'row-action danger' : 'row-action'} onClick={() => onToggle(item.id)}>{item.is_active ? 'Khóa' : 'Mở khóa'}</button></td></tr>)}</tbody></table></div></section>{editing && <EditUserModal user={editing} onClose={() => setEditing(null)} onEdit={async (data) => { await onEdit(editing.id, data); setEditing(null) }} />}</div>
}

function ChangePasswordModal({ onClose, onChange }: { onClose: () => void; onChange: (data: { current_password: string; new_password: string }) => Promise<void> }) {
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); try { await onChange({ current_password: String(data.get('current_password')), new_password: String(data.get('new_password')) }) } catch (submitError) { setError(submitError instanceof Error ? submitError.message : 'Không thể đổi mật khẩu') } }
  return <div className="modal-backdrop"><section className="modal"><div className="modal-header"><div><p className="eyebrow blue">BẢO MẬT TÀI KHOẢN</p><h2>Đổi mật khẩu</h2></div><button className="close-button" onClick={onClose}>×</button></div><form onSubmit={submit} className="create-form"><label>Mật khẩu hiện tại<input name="current_password" type="password" required /></label><label>Mật khẩu mới<input name="new_password" type="password" minLength={8} placeholder="Ít nhất 8 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt" required /></label>{error && <div className="form-error">{error}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit">Cập nhật</button></div></form></section></div>
}

function EditUserModal({ user, onClose, onEdit }: { user: User; onClose: () => void; onEdit: (data: { full_name: string; email: string }) => Promise<void> }) {
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); try { await onEdit({ full_name: String(data.get('full_name')), email: String(data.get('email')) }) } catch (submitError) { setError(submitError instanceof Error ? submitError.message : 'Không thể cập nhật tài khoản') } }
  return <div className="modal-backdrop"><section className="modal"><div className="modal-header"><div><p className="eyebrow blue">THÔNG TIN TÀI KHOẢN</p><h2>Chỉnh sửa</h2></div><button className="close-button" onClick={onClose}>×</button></div><form onSubmit={submit} className="create-form"><label>Họ và tên<input name="full_name" defaultValue={user.full_name} required /></label><label>Email<input name="email" type="email" defaultValue={user.email} required /></label>{error && <div className="form-error">{error}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit">Lưu thay đổi</button></div></form></section></div>
}

function CreateUserModal({ onClose, onCreate }: { onClose: () => void; onCreate: (data: { full_name: string; email: string; password: string; role: Role }) => Promise<void> }) {
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); try { await onCreate({ full_name: String(data.get('full_name')), email: String(data.get('email')), password: String(data.get('password')), role: String(data.get('role')) as Role }) } catch (submitError) { setError(submitError instanceof Error ? submitError.message : 'Không thể tạo tài khoản') } }
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="modal"><div className="modal-header"><div><p className="eyebrow blue">TÀI KHOẢN MỚI</p><h2>Tạo tài khoản</h2></div><button className="close-button" onClick={onClose}>×</button></div><form onSubmit={submit} className="create-form"><label>Họ và tên<input name="full_name" required /></label><label>Email<input name="email" type="email" required /></label><div className="form-row"><label>Mật khẩu<input name="password" type="password" minLength={8} placeholder="Ít nhất 8 ký tự, gồm chữ hoa, chữ thường, số và ký tự đặc biệt" required /></label><label>Vai trò<select name="role" defaultValue="lecturer"><option value="lecturer">Giảng viên</option><option value="accountant">Kế toán</option><option value="admin">Quản trị viên</option></select></label></div>{error && <div className="form-error">{error}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>Hủy</button><button className="primary-button" type="submit">Tạo tài khoản</button></div></form></section></div>
}

export default App
