using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace tms_backend.Controllers
{
    [Authorize(Roles = "Admin")]
    [ApiController]
    [Route("api/[controller]")]
    public class UserRoleController : ControllerBase
    {
        private readonly UserManager<IdentityUser> _userManager;
        private readonly RoleManager<IdentityRole> _roleManager;

        public UserRoleController(UserManager<IdentityUser> userManager, RoleManager<IdentityRole> roleManager)
        {
            _userManager = userManager;
            _roleManager = roleManager;
        }

        // 1. Phân bổ vai trò (Assign Role)
        [HttpPost("assign-role")]
        public async Task<IActionResult> AssignRole(string userId, string roleName)
        {
            var user = await _userManager.FindByIdAsync(userId);
            if (user == null) return NotFound("Không tìm thấy người dùng.");

            if (!await _roleManager.RoleExistsAsync(roleName))
                return BadRequest("Vai trò không tồn tại.");

            var result = await _userManager.AddToRoleAsync(user, roleName);
            if (result.Succeeded)
            {
                // Cập nhật SecurityStamp để quyền mới có hiệu lực ngay
                await _userManager.UpdateSecurityStampAsync(user);
                return Ok(new { message = $"Đã gán vai trò {roleName} thành công." });
            }
            return BadRequest(result.Errors);
        }

        // 2. Thu hồi vai trò (Revoke Role)
        [HttpPost("revoke-role")]
        public async Task<IActionResult> RevokeRole(string userId, string roleName)
        {
            var currentUserId = User.FindFirstValue(ClaimTypes.NameIdentifier);

            // Kiểm tra quy tắc: Không cho phép tự thu hồi quyền Admin của chính mình
            if (userId == currentUserId && roleName.Equals("Admin", StringComparison.OrdinalIgnoreCase))
            {
                return BadRequest("Bạn không thể tự thu hồi vai trò Quản trị của chính mình!");
            }

            var user = await _userManager.FindByIdAsync(userId);
            if (user == null) return NotFound("Không tìm thấy người dùng.");

            var result = await _userManager.RemoveFromRoleAsync(user, roleName);
            if (result.Succeeded)
            {
                await _userManager.UpdateSecurityStampAsync(user);
                return Ok(new { message = $"Đã thu hồi vai trò {roleName} thành công." });
            }
            return BadRequest(result.Errors);
        }
    }
}