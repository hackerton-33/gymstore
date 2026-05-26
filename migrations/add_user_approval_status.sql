-- Add approval_status column to users table
ALTER TABLE users ADD COLUMN approval_status VARCHAR(20) DEFAULT 'pending';

-- Add approved_by column (foreign key to users table)
ALTER TABLE users ADD COLUMN approved_by INTEGER REFERENCES users(id);

-- Add approved_at column (datetime)
ALTER TABLE users ADD COLUMN approved_at DATETIME;

-- Update existing users to have 'approved' status
UPDATE users SET approval_status = 'approved' WHERE role = 'admin';

-- Update other existing users to 'approved' for existing data
UPDATE users SET approval_status = 'approved' WHERE approval_status IS NULL;

-- Create index for approval_status
CREATE INDEX idx_users_approval_status ON users(approval_status);
