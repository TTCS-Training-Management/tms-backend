// ========================================
// BIẾN TOÀN CỤC
// ========================================

let currentCourseId = null;


// ========================================
// KHI TRANG ĐƯỢC TẢI
// ========================================

document.addEventListener("DOMContentLoaded", function () {
    loadCourses();
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