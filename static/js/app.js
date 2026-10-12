// ========================================
// BIẾN TOÀN CỤC
// ========================================

let currentCourseId = null;


// ========================================
// KHI TRANG ĐƯỢC TẢI
// ========================================

document.addEventListener("DOMContentLoaded", function () {
    loadCourses();
    loadClasses();
});


// ========================================
// HIỂN THỊ THÔNG BÁO
// ========================================

function showNotification(message, type = "success") {
    const notification = document.getElementById("notification");

    notification.textContent = message;
    notification.className = `notification show ${type}`;

    setTimeout(() => {
        notification.className = "notification";
    }, 3000);
}


// ========================================
// MỞ MODAL
// ========================================

function openModal(modalId) {
    const modal = document.getElementById(modalId);

    if (modal) {
        modal.classList.add("show");
    }
}


// ========================================
// ĐÓNG MODAL
// ========================================

function closeModal(modalId) {
    const modal = document.getElementById(modalId);

    if (modal) {
        modal.classList.remove("show");
    }
}


// ========================================
// MODAL TẠO MÔN HỌC
// ========================================

function openCreateCourseModal() {

    document.getElementById("courseId").value = "";
    document.getElementById("courseName").value = "";
    document.getElementById("totalLessons").value = "";

    openModal("createCourseModal");
}


// ========================================
// LẤY DANH SÁCH MÔN HỌC
// ========================================

async function loadCourses() {

    const tableBody = document.getElementById("courseTableBody");

    tableBody.innerHTML = `
        <tr>
            <td colspan="4" class="text-center">
                Đang tải dữ liệu...
            </td>
        </tr>
    `;

    try {

        const response = await fetch("/api/courses");

        if (!response.ok) {
            throw new Error("Không thể lấy danh sách môn học.");
        }

        const data = await response.json();

        const courses = data.courses || [];

        renderCourses(courses);

    } catch (error) {

        console.error(error);

        tableBody.innerHTML = `
            <tr>
                <td colspan="4" class="text-center">
                    Không thể tải danh sách môn học.
                </td>
            </tr>
        `;

        showNotification(
            error.message,
            "error"
        );
    }
}


// ========================================
// HIỂN THỊ DANH SÁCH MÔN HỌC
// ========================================

function renderCourses(courses) {

    const tableBody = document.getElementById("courseTableBody");

    if (!courses || courses.length === 0) {

        tableBody.innerHTML = `
            <tr>
                <td colspan="4" class="text-center">
                    Chưa có môn học.
                </td>
            </tr>
        `;

        return;
    }


    tableBody.innerHTML = courses.map(course => {

        const courseId =
            course.id ??
            course.course_id;

        const courseName =
            course.name ??
            course.course_name ??
            "Không có tên";

        const totalLessons =
            course.total_lessons ??
            course.totalLessons ??
            0;


        return `
            <tr>

                <td>
                    ${escapeHtml(String(courseId))}
                </td>

                <td>
                    <strong>
                        ${escapeHtml(String(courseName))}
                    </strong>
                </td>

                <td>
                    ${escapeHtml(String(totalLessons))}
                </td>

                <td>

                    <button
                        class="btn btn-primary btn-small"
                        onclick="viewCourse(${courseId})">
                        Xem
                    </button>

                </td>

            </tr>
        `;

    }).join("");
}


// ========================================
// TẠO MÔN HỌC
// ========================================

async function createCourse(event) {

    event.preventDefault();


    const courseId =
        document.getElementById("courseId").value;

    const courseName =
        document.getElementById("courseName").value.trim();

    const totalLessons =
        document.getElementById("totalLessons").value;


    if (!courseId || !courseName || !totalLessons) {

        showNotification(
            "Vui lòng nhập đầy đủ thông tin.",
            "error"
        );

        return;
    }


    try {

        const response = await fetch("/api/courses", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({

                id: Number(courseId),

                name: courseName,

                total_lessons: Number(totalLessons)

            })

        });


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.message ||
                "Không thể tạo môn học."
            );

        }


        closeModal("createCourseModal");


        showNotification(
            data.message ||
            "Tạo môn học thành công."
        );


        loadCourses();


    } catch (error) {

        console.error(error);

        showNotification(
            error.message,
            "error"
        );
    }
}


// ========================================
// XEM CHI TIẾT MÔN HỌC
// ========================================

async function viewCourse(courseId) {

    currentCourseId = courseId;


    const detailName =
        document.getElementById("detailCourseName");

    const detailContent =
        document.getElementById("courseDetailContent");


    detailName.textContent =
        "Chi tiết môn học";


    detailContent.innerHTML =
        "<p>Đang tải dữ liệu...</p>";


    openModal("courseDetailModal");


    try {

        const response = await fetch(
            `/api/courses/${courseId}`
        );


        const course = await response.json();


        if (!response.ok) {

            throw new Error(
                course.message ||
                "Không thể lấy thông tin môn học."
            );

        }


        displayCourseDetail(course);


    } catch (error) {

        console.error(error);

        detailContent.innerHTML = `
            <p>
                Không thể tải thông tin môn học.
            </p>
        `;

        showNotification(
            error.message,
            "error"
        );
    }
}


// ========================================
// HIỂN THỊ CHI TIẾT MÔN HỌC
// ========================================

function displayCourseDetail(course) {

    const detailName =
        document.getElementById("detailCourseName");

    const detailContent =
        document.getElementById("courseDetailContent");


    const courseName =
        course.name ??
        course.course_name ??
        "Không có tên";


    const courseId =
        course.id ??
        course.course_id ??
        currentCourseId;


    const lessons =
        course.lessons || [];


    detailName.textContent =
        courseName;


    let html = `

        <div class="course-info">

            <p>
                <strong>ID:</strong>
                ${escapeHtml(String(courseId))}
            </p>

            <p>
                <strong>Số buổi học:</strong>
                ${lessons.length}
            </p>

        </div>

        <div class="lesson-list">

            <h3>Danh sách buổi học</h3>
    `;


    if (lessons.length === 0) {

        html += `
            <p>
                Chưa có buổi học nào.
            </p>
        `;

    } else {

        lessons.forEach((lesson, index) => {

            const order =
                lesson.order ??
                lesson.lesson_order ??
                index + 1;

            const topic =
                lesson.topic ??
                "Chưa có chủ đề";

            const objective =
                lesson.objective ??
                "Chưa có mục tiêu";


            html += `

                <div class="lesson-card">

                    <h4>
                        Buổi ${escapeHtml(String(order))}
                        - ${escapeHtml(String(topic))}
                    </h4>

                    <p>
                        ${escapeHtml(String(objective))}
                    </p>

                </div>

            `;
        });
    }


    html += `
        </div>
    `;


    detailContent.innerHTML = html;
}


// ========================================
// MODAL THÊM BUỔI HỌC
// ========================================

function openAddLessonModal() {

    if (!currentCourseId) {

        showNotification(
            "Chưa chọn môn học.",
            "error"
        );

        return;
    }


    document.getElementById("lessonOrder").value = "";
    document.getElementById("lessonTopic").value = "";
    document.getElementById("lessonObjective").value = "";


    openModal("addLessonModal");
}


// ========================================
// THÊM BUỔI HỌC
// ========================================

async function addLesson(event) {

    event.preventDefault();


    if (!currentCourseId) {

        showNotification(
            "Chưa chọn môn học.",
            "error"
        );

        return;
    }


    const order =
        document.getElementById("lessonOrder").value;

    const topic =
        document.getElementById("lessonTopic").value.trim();

    const objective =
        document.getElementById("lessonObjective").value.trim();


    if (!order || !topic || !objective) {

        showNotification(
            "Vui lòng nhập đầy đủ thông tin.",
            "error"
        );

        return;
    }


    try {

        const response = await fetch(
            `/api/courses/${currentCourseId}/lessons`,
            {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({

                    order: Number(order),

                    topic: topic,

                    objective: objective

                })

            }
        );


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.message ||
                "Không thể thêm buổi học."
            );
        }


        closeModal("addLessonModal");


        showNotification(
            data.message ||
            "Thêm buổi học thành công."
        );


        viewCourse(currentCourseId);


    } catch (error) {

        console.error(error);

        showNotification(
            error.message,
            "error"
        );
    }
}


// ========================================
// ESCAPE HTML
// ========================================

function escapeHtml(value) {

    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


// ========================================
// CLICK RA NGOÀI MODAL ĐỂ ĐÓNG
// ========================================

document.addEventListener("click", function (event) {

    if (event.target.classList.contains("modal")) {

        event.target.classList.remove("show");

    }

});


/* ========================================
   QUẢN LÝ LỚP HỌC
======================================== */

async function loadPrograms() {
    const select = document.getElementById("classProgram");
    if (!select) return;

    try {
        const response = await fetch("/api/programs");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Không thể tải chương trình đào tạo.");
        }

        const programs = Array.isArray(data) ? data : (data.programs || []);

        select.innerHTML = '<option value="">-- Chọn chương trình --</option>';

        programs.forEach(program => {
            const option = document.createElement("option");
            option.value = program.id;
            option.textContent = `${program.id} - ${program.name}`;
            select.appendChild(option);
        });

        if (programs.length === 0) {
            select.innerHTML = '<option value="">Chưa có chương trình đào tạo</option>';
        }
    } catch (error) {
        console.error(error);
        select.innerHTML = '<option value="">Không thể tải chương trình</option>';
        showNotification(error.message, "error");
    }
}

function openCreateClassModal() {
    const form = document.querySelector("#createClassModal form");

    if (form) form.reset();

    openModal("createClassModal");
    loadPrograms();
}

async function createClass(event) {
    event.preventDefault();

    const classCode = document.getElementById("classCode").value.trim();
    const programId = document.getElementById("classProgram").value;
    const openingDate = document.getElementById("classOpeningDate").value;
    const maxStudents = document.getElementById("classMaxStudents").value;
    const learningMode = document.getElementById("classLearningMode").value;

    if (!classCode || !programId || !openingDate || !maxStudents || !learningMode) {
        showNotification("Vui lòng nhập đầy đủ thông tin lớp học.", "error");
        return;
    }

    try {
        const response = await fetch("/api/classes", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                class_code: classCode,
                program_id: programId,
                opening_date: openingDate,
                max_students: Number(maxStudents),
                learning_mode: learningMode
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Không thể tạo lớp học.");
        }

        closeModal("createClassModal");
        showNotification(data.message || "Mở lớp học mới thành công.");
        await loadClasses();
    } catch (error) {
        console.error(error);
        showNotification(error.message, "error");
    }
}

async function loadClasses() {
    const tableBody = document.getElementById("classTableBody");
    if (!tableBody) return;

    tableBody.innerHTML = `
        <tr>
            <td colspan="7" class="text-center">Đang tải danh sách lớp...</td>
        </tr>
    `;

    try {
        const response = await fetch("/api/classes");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Không thể tải danh sách lớp.");
        }

        const classes = Array.isArray(data) ? data : (data.classes || []);
        renderClasses(classes);
    } catch (error) {
        console.error(error);
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center">Không thể tải danh sách lớp.</td>
            </tr>
        `;
        showNotification(error.message, "error");
    }
}

function renderClasses(classes) {
    const tableBody = document.getElementById("classTableBody");
    if (!tableBody) return;

    if (!classes || classes.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center">Chưa có lớp học.</td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = classes.map(item => {
        const classCode = item.class_code || "";
        const status = item.status || "Chuẩn bị";
        const transitions = {
            "Chuẩn bị": ["Đang học", "Huỷ"],
            "Đang học": ["Kết thúc", "Huỷ"],
            "Kết thúc": [],
            "Huỷ": []
        };

        const options = (transitions[status] || [])
            .map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
            .join("");

        const statusControl = options
            ? `<select id="status-${escapeHtml(classCode)}">${options}</select>
               <button class="btn btn-secondary btn-small"
                       onclick="updateClassStatus('${escapeHtml(classCode)}')">
                   Cập nhật
               </button>`
            : escapeHtml(status);

        return `
            <tr>
                <td><strong>${escapeHtml(classCode)}</strong></td>
                <td>${escapeHtml(item.program_name || item.program_id || "")}</td>
                <td>${escapeHtml(item.opening_date || "")}</td>
                <td>${escapeHtml(String(item.max_students ?? ""))}</td>
                <td>${escapeHtml(item.learning_mode || "")}</td>
                <td>${statusControl}</td>
                <td>
                    <button class="btn btn-primary btn-small"
                            onclick="viewClass('${escapeHtml(classCode)}')">
                        Chi tiết
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

async function updateClassStatus(classCode) {
    const select = document.getElementById(`status-${classCode}`);
    if (!select) return;

    try {
        const response = await fetch(
            `/api/classes/${encodeURIComponent(classCode)}/status`,
            {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ status: select.value })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Không thể cập nhật trạng thái lớp.");
        }

        showNotification(data.message || "Cập nhật trạng thái thành công.");
        await loadClasses();
    } catch (error) {
        console.error(error);
        showNotification(error.message, "error");
    }
}

async function viewClass(classCode) {
    try {
        const response = await fetch(`/api/classes/${encodeURIComponent(classCode)}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Không thể tải chi tiết lớp.");
        }

        const item = data.class || data;

        const courseList = (item.courses || []).map(course => `
            <li>
                ${escapeHtml(String(course.name || "Không có tên"))}
                — ${escapeHtml(String(course.total_lessons ?? 0))} buổi
            </li>
        `).join("");

        const details = `
            <p><strong>Mã lớp:</strong> ${escapeHtml(item.class_code || "")}</p>
            <p><strong>Chương trình:</strong> ${escapeHtml(item.program_name || "")}</p>
            <p><strong>Ngày khai giảng:</strong> ${escapeHtml(item.opening_date || "")}</p>
            <p><strong>Sĩ số tối đa:</strong> ${escapeHtml(String(item.max_students ?? ""))}</p>
            <p><strong>Hình thức học:</strong> ${escapeHtml(item.learning_mode || "")}</p>
            <p><strong>Trạng thái:</strong> ${escapeHtml(item.status || "")}</p>
            <h3>Danh sách môn học được sao chép</h3>
            <ul>${courseList || "<li>Chưa có môn học</li>"}</ul>
        `;

        let detailModal = document.getElementById("classDetailModal");

        if (!detailModal) {
            detailModal = document.createElement("div");
            detailModal.id = "classDetailModal";
            detailModal.className = "modal";
            detailModal.innerHTML = `
                <div class="modal-content modal-large">
                    <div class="modal-header">
                        <h2>Chi tiết lớp học</h2>
                        <button class="modal-close" onclick="closeModal('classDetailModal')">&times;</button>
                    </div>
                    <div id="classDetailContent"></div>
                    <div class="modal-actions">
                        <button class="btn btn-secondary" onclick="closeModal('classDetailModal')">Đóng</button>
                    </div>
                </div>
            `;
            document.querySelector(".container").appendChild(detailModal);
        }

        document.getElementById("classDetailContent").innerHTML = details;
        openModal("classDetailModal");
    } catch (error) {
        console.error(error);
        showNotification(error.message, "error");
    }
}
