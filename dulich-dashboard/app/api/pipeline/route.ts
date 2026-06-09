import { NextResponse } from "next/server";
import { exec } from "child_process";
import path from "path";
import fs from "fs";
import { addVideo } from "@/lib/mock_db";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { topic, templateId, creator } = body;

    if (!topic || typeof topic !== "string" || topic.trim().length === 0) {
      return NextResponse.json(
        { success: false, error: "Chủ đề là bắt buộc" },
        { status: 400 },
      );
    }

    const cleanTopic = topic.trim();
    const pipelineDir = path.join(process.cwd(), "..", "dulich-pipeline");
    const pythonExec = path.join(pipelineDir, ".venv", "Scripts", "python.exe");
    const mainScript = path.join(pipelineDir, "main.py");

    // Check if running on Vercel or cloud environment
    if (process.env.VERCEL || !fs.existsSync(pythonExec)) {
      return NextResponse.json(
        {
          success: false,
          error: "Không thể chạy Python Pipeline trực tiếp từ Cloud (Vercel)!",
          details: "Do Dashboard đang chạy ở chế độ Production trên Vercel, server không thể can thiệp vào máy local của bạn. Hãy chạy pipeline trực tiếp từ terminal local của bạn bằng lệnh:\n\npython main.py --topic \"" + cleanTopic + "\"\n\nPipeline sẽ tự động đồng bộ kết quả lên đây nhờ vào cấu hình DASHBOARD_URL trong file .env local.",
        },
        { status: 400 },
      );
    }

    // Run the Python pipeline
    const command = `"${pythonExec}" "${mainScript}" --topic "${cleanTopic}"`;
    
    console.log(`Running pipeline command: ${command}`);

    return new Promise<NextResponse>((resolve) => {
      exec(command, { cwd: pipelineDir }, (error, stdout, stderr) => {
        if (error) {
          console.error(`Pipeline execution error: ${error}`);
          console.error(`Stderr: ${stderr}`);
          resolve(
            NextResponse.json(
              {
                success: false,
                error: "Lỗi khi chạy Python Pipeline trên máy local",
                details: error.message,
                stderr,
              },
              { status: 500 },
            )
          );
          return;
        }

        console.log(`Pipeline output:\n${stdout}`);

        // Extract Video Path
        const videoMatch = stdout.match(/Video:\s+(.+)/);
        const relativeVideoPath = videoMatch ? videoMatch[1].trim() : "";
        const absoluteVideoPath = relativeVideoPath
          ? path.resolve(pipelineDir, relativeVideoPath)
          : "";

        // Fallback or Mock script data
        const script = {
          hook: `Bạn đã nghe về danh lam thắng cảnh ${cleanTopic} chưa? 🔥`,
          body: `Hôm nay mình đưa các bạn khám phá toàn bộ vẻ đẹp tuyệt vời tại ${cleanTopic} trong vòng 60 giây!\n\nĐầu tiên là cảnh đẹp thiên nhiên hùng vĩ, không khí trong lành, con người nồng hậu.\n\nMình đã ở đây trải nghiệm và vô cùng ấn tượng với ẩm thực cũng như các điểm check-in cực đỉnh.`,
          cta: `Thả tim ❤️ và Follow để cùng mình khám phá thêm nhiều địa điểm du lịch thú vị khác nhé!`,
        };

        const captions = {
          hooks: [`Khám phá ${cleanTopic}!`, `Review chi tiết ${cleanTopic}`, `${cleanTopic} có gì hot?`],
          caption_short: `🌟 Khám phá vẻ đẹp ${cleanTopic} ngay hôm nay! #travel #${cleanTopic.replace(/\s+/g, "").toLowerCase()}`,
          caption_long: `✈️ Review chi tiết hành trình khám phá ${cleanTopic} cực hot!\n\n🏖️ Thiên nhiên kỳ thú\n🍜 Ẩm thực đa dạng\n💰 Chi phí tự túc cực kỳ tiết kiệm\n\n#dulich #${cleanTopic.replace(/\s+/g, "").toLowerCase()} #vietnam #review`,
          hashtags: ["#dulich", `#${cleanTopic.replace(/\s+/g, "").toLowerCase()}`, "#vietnam", "#travel"],
        };

        const images = {
          description: `Bộ ảnh gợi ý cho ${cleanTopic}`,
          prompts: [
            `Landscape of ${cleanTopic}, wide view, cinematic`,
            `Local food in ${cleanTopic}, close up shot`,
            `Sunset over ${cleanTopic}, golden hour`,
          ],
        };

        // Add to our Mock DB
        const creatorName = creator ? `Creator ${creator}` : "AI Pipeline";
        const newVideo = addVideo({
          name: `Video ${cleanTopic} (Local Run)`,
          creator: creatorName,
          topic: cleanTopic,
          templateId: templateId || "default",
          seeds: [],
          script,
          captions,
          images,
        });

        // Update video item status to show it is finished rendering
        newVideo.status = "Chờ duyệt";

        resolve(
          NextResponse.json({
            success: true,
            message: "Pipeline đã chạy thành công trên máy local!",
            data: {
              ...newVideo,
              videoPath: absoluteVideoPath,
              stdout,
            },
          })
        );
      });
    });

  } catch (error) {
    console.error("Pipeline API error:", error);
    return NextResponse.json(
      {
        success: false,
        error: "Lỗi hệ thống khi gọi pipeline",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}
