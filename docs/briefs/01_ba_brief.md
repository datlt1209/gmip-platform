# Brief 01 — PM → Business Analyst

**Dự án:** Nền tảng theo dõi chỉ số kinh tế thế giới và báo cáo hàng ngày
**Từ:** Project Manager · **Gửi:** Business Analyst · **Ngày:** 13/10/2026
**Kế hoạch gốc:** `project_plan.md` (đã được chủ đề bài duyệt)

## 1. Bối cảnh
Chủ đề bài muốn một website tự động tổng hợp dữ liệu kinh tế từ internet và mỗi ngày trả về báo cáo phân tích xu hướng kinh tế thế giới, để nắm bắt tình hình thị trường.

## 2. Giả định mặc định (chủ đề bài chưa xác nhận — hãy nêu rõ nếu bạn thấy bất hợp lý)

| # | Nội dung | Giả định |
|---|---|---|
| 1 | Công nghệ frontend | Next.js (chưa chốt; Flutter Web là phương án thay thế) |
| 2 | Ngôn ngữ giao diện/báo cáo | Tiếng Việt là chính; chưa làm đa ngôn ngữ |
| 3 | Phạm vi thị trường | Thế giới; Việt Nam là mục tùy chọn nếu dữ liệu sẵn |
| 4 | Ngân sách dữ liệu | Chỉ dùng nguồn miễn phí |
| 5 | Giờ phát hành | 07:00 giờ Việt Nam (Asia/Ho_Chi_Minh); dùng cá nhân trước, chưa công khai |

## 3. Nhiệm vụ của BA

1. **Danh mục chỉ số:** chốt danh sách chỉ số MVP (gợi ý trong kế hoạch: vĩ mô, lãi suất/trái phiếu, chứng khoán, tiền tệ, hàng hóa, tâm lý rủi ro). Với mỗi chỉ số ghi: tên, mã, đơn vị, tần suất cập nhật, độ ưu tiên.
2. **Khảo sát nguồn dữ liệu:** với mỗi chỉ số, đề xuất nguồn chính và nguồn dự phòng (ví dụ FRED, World Bank, IMF, ECB, Yahoo Finance/Stooq, RSS tin tức). Ghi: cách truy cập, giới hạn tốc độ, yêu cầu API key, điều khoản sử dụng, độ trễ dữ liệu.
3. **Logic phân tích xu hướng:** định nghĩa công thức rõ ràng (thay đổi 1 ngày/1 tuần/1 tháng, đường trung bình, so với cùng kỳ, ngưỡng "tăng mạnh/giảm mạnh"), đủ cụ thể để Backend lập trình và Tester kiểm chứng.
4. **Cấu trúc báo cáo hàng ngày:** các mục, độ dài, văn phong, cách trình bày số liệu, mục "điểm cần chú ý" và "rủi ro". Nêu quy tắc: mọi con số trong báo cáo phải truy ngược được về dữ liệu đã lưu.
5. **User story và tiêu chí chấp nhận** cho: dashboard, trang chi tiết chỉ số, báo cáo hàng ngày, kho lưu báo cáo, cập nhật dữ liệu tự động, xử lý lỗi nguồn dữ liệu.
6. **Yêu cầu phi chức năng:** hiệu năng, độ tin cậy của job hàng ngày, lưu trữ lịch sử, ghi log, bảo mật cơ bản.
7. **Rủi ro và câu hỏi mở** phát sinh trong quá trình phân tích.

## 4. Sản phẩm bàn giao
- Tài liệu đặc tả nghiệp vụ (BRD/SRS) gồm các mục 1–6 ở trên.
- Danh mục chỉ số và nguồn dữ liệu (dạng bảng).
- Mẫu báo cáo hàng ngày (một bản mẫu hoàn chỉnh).
- Danh sách user story kèm tiêu chí chấp nhận (Tester sẽ dùng làm cơ sở kiểm thử).

## 5. Quy tắc phối hợp
- BA gửi đặc tả cho **PM** duyệt trước; không gửi thẳng cho Dev team.
- Chỉ sau khi PM và chủ đề bài duyệt (Gate 1), đặc tả mới được chuyển cho Frontend Designer và Backend Developer.
- Việc gì ngoài phạm vi MVP (tài khoản người dùng, cảnh báo, dự báo ML, app di động) ghi vào mục "để sau", không đưa vào đặc tả MVP.
