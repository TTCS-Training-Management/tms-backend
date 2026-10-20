using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using TTCS.EducationManagement.API.Data;
using TTCS.EducationManagement.API.DTOs;
using TTCS.EducationManagement.API.Models;

namespace TTCS.EducationManagement.API.Services
{
    public class AuthService : IAuthService
    {
        private readonly ApplicationDbContext _context;
        private readonly IConfiguration _configuration;

        public AuthService(ApplicationDbContext context, IConfiguration configuration)
        {
            _context = context;
            _configuration = configuration;
        }

        public async Task LoginAsync(LoginRequestDto request)
        {
            var user = await _context.Users
                .Include(u => u.UserRoles)
                .ThenInclude(ur => ur.Role)
                .FirstOrDefaultAsync(u => u.Email == request.Email);

            if (user == null) return null;

            // Kiểm tra trạng thái khóa tài khoản
            if (user.IsLocked)
            {
                if (user.LockoutEnd.HasValue && user.LockoutEnd.Value <= DateTime.Now)
                {
                    // Hết thời gian khóa -> Tự động mở khóa
                    user.IsLocked = false;
                    user.FailedLoginAttempts = 0;
                    user.LockoutEnd = null;
                    user.LockReason = null;
                }
                else
                {
                    throw new Exception("Tài khoản của bạn đã bị khóa do nhập sai mật khẩu nhiều lần. Vui lòng thử lại sau.");
                }
            }

            // Kiểm tra mật khẩu băm
            bool isPasswordValid = BCrypt.Net.BCrypt.Verify(request.Password, user.PasswordHash);

            if (!isPasswordValid)
            {
                user.FailedLoginAttempts += 1;

                // Khóa tài khoản sau 5 lần sai liên tiếp (S1-01 / EP-01)
                if (user.FailedLoginAttempts >= 5)
                {
                    user.IsLocked = true;
                    user.LockoutEnd = DateTime.Now.AddMinutes(15); // Khóa 15 phút
                    user.LockReason = "Nhập sai mật khẩu quá 5 lần liên tiếp";
                }

                await _context.SaveChangesAsync();
                return null;
            }

            // Đăng nhập thành công -> Reset số lần sai
            user.FailedLoginAttempts = 0;
            user.LockoutEnd = null;
            await _context.SaveChangesAsync();

            // Tạo danh sách Roles
            var roles = user.UserRoles.Select(ur => ur.Role.RoleCode).ToList();

            // Tạo Token JWT
            var token = GenerateJwtToken(user, roles);

            return new LoginResponseDto
            {
                Token = token,
                Email = user.Email,
                FullName = user.FullName,
                Roles = roles
            };
        }

        public async Task RegisterAsync(RegisterUserDto request)
        {
            if (await _context.Users.AnyAsync(u => u.Email == request.Email))
            {
                return false; // Email đã tồn tại
            }

            var passwordHash = BCrypt.Net.BCrypt.HashPassword(request.Password);

            var user = new User
            {
                FullName = request.FullName,
                Email = request.Email,
                PasswordHash = passwordHash,
                IsActive = true
            };

            _context.Users.Add(user);
            await _context.SaveChangesAsync();

            // Gán Role mặc định
            var role = await _context.Roles.FirstOrDefaultAsync(r => r.RoleCode == request.RoleCode)
                       ?? await _context.Roles.FirstOrDefaultAsync(r => r.RoleCode == "Student");

            if (role != null)
            {
                _context.UserRoles.Add(new UserRole
                {
                    UserId = user.Id,
                    RoleId = role.Id
                });
                await _context.SaveChangesAsync();
            }

            return true;
        }

        private string GenerateJwtToken(User user, List roles)
        {
            var authClaims = new List
            {
                new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
                new Claim(ClaimTypes.Email, user.Email),
                new Claim(ClaimTypes.Name, user.FullName)
            };

            foreach (var role in roles)
            {
                authClaims.Add(new Claim(ClaimTypes.Role, role));
            }

            var jwtKey = _configuration["Jwt:Key"] ?? "Chuoi_Secret_Key_Bao_Mat_Toi_Thieu_32_Ky_Tu_TTCS_2026";
            var authSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtKey));

            var token = new JwtSecurityToken(
                issuer: _configuration["Jwt:Issuer"],
                audience: _configuration["Jwt:Audience"],
                expires: DateTime.Now.AddMinutes(double.Parse(_configuration["Jwt:ExpireMinutes"] ?? "120")),
                claims: authClaims,
                signingCredentials: new SigningCredentials(authSigningKey, SecurityAlgorithms.HmacSha256)
            );

            return new JwtSecurityTokenHandler().WriteToken(token);
        }
    }
}