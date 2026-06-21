-- Tạo tài khoản admin
-- Username: admin
-- Password: admin@123

INSERT INTO users (username, password, role, name, hook_style, voice) 
VALUES ('admin', 'admin@123', 'admin', 'Quản trị viên', 'hook_red', 'gtts')
ON CONFLICT (username) 
DO UPDATE SET 
  password = 'admin@123',
  role = 'admin',
  name = 'Quản trị viên',
  updated_at = NOW();
