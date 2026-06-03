(function () {
  const canvas = document.getElementById("spendingChart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"];
  const income = [82, 88, 90, 96, 92, 99];
  const expenses = [54, 57, 60, 63, 58, 61];
  const savings = [28, 31, 30, 33, 34, 38];

  const w = canvas.width;
  const h = canvas.height;
  const pad = { top: 30, right: 30, bottom: 50, left: 52 };
  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;

  function yScale(v) {
    const max = 110;
    return pad.top + chartH - (v / max) * chartH;
  }

  function roundTopBar(x, y, bw, bh, color) {
    const r = 6;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x, y + bh);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.lineTo(x + bw - r, y);
    ctx.quadraticCurveTo(x + bw, y, x + bw, y + r);
    ctx.lineTo(x + bw, y + bh);
    ctx.closePath();
    ctx.fill();
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);

    ctx.strokeStyle = "#d5deed";
    ctx.fillStyle = "#64748b";
    ctx.font = "12px Segoe UI";

    for (let i = 0; i <= 5; i += 1) {
      const value = i * 20;
      const y = yScale(value);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
      ctx.fillText("₹" + value + "k", 10, y + 4);
    }

    const groupW = chartW / months.length;
    const barW = 14;

    months.forEach((m, i) => {
      const gx = pad.left + i * groupW + groupW / 2;
      const yi = yScale(income[i]);
      const ye = yScale(expenses[i]);
      const ys = yScale(savings[i]);

      roundTopBar(gx - 20, yi, barW, pad.top + chartH - yi, "#1a3c8f");
      roundTopBar(gx - 2, ye, barW, pad.top + chartH - ye, "#ef4444");
      roundTopBar(gx + 16, ys, barW, pad.top + chartH - ys, "#10b981");

      ctx.fillStyle = "#334155";
      ctx.fillText(m, gx - 12, h - 20);
    });

    ctx.save();
    ctx.setLineDash([6, 5]);
    ctx.strokeStyle = "#f97316";
    ctx.lineWidth = 2;
    ctx.beginPath();
    months.forEach((_, i) => {
      const gx = pad.left + i * groupW + groupW / 2 - 12;
      const yi = yScale(income[i]);
      if (i === 0) ctx.moveTo(gx, yi);
      else ctx.lineTo(gx, yi);
    });
    ctx.stroke();
    ctx.restore();

    const legends = [
      { name: "Income", color: "#1a3c8f" },
      { name: "Expenses", color: "#ef4444" },
      { name: "Savings", color: "#10b981" },
      { name: "Income Trend", color: "#f97316" }
    ];

    legends.forEach((l, i) => {
      const x = pad.left + i * 130;
      ctx.fillStyle = l.color;
      ctx.fillRect(x, 8, 14, 14);
      ctx.fillStyle = "#334155";
      ctx.fillText(l.name, x + 20, 19);
    });
  }

  draw();
})();
