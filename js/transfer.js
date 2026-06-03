(function () {
  const tabs = document.querySelectorAll(".transfer-tab");
  const bankModeFields = document.getElementById("bankModeFields");
  const upiModeFields = document.getElementById("upiModeFields");
  const transferForm = document.getElementById("transferForm");
  const verifyIfsc = document.getElementById("verifyIfsc");
  const ifsc = document.getElementById("ifsc");
  const bankName = document.getElementById("bankName");
  const overlay = document.getElementById("successOverlay");
  const successDetails = document.getElementById("successDetails");
  const newTransferBtn = document.getElementById("newTransferBtn");
  const togglePin = document.getElementById("togglePin");
  const authCode = document.getElementById("authCode");

  if (!transferForm) return;

  const ifscMap = {
    NEXA: "NexaBank NA",
    CITI: "Citi National Bank",
    WFCX: "Wells Core Financial",
    CHAS: "Chase Metropolitan"
  };

  let mode = "NEFT";

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      mode = tab.dataset.mode;

      const isUPI = mode === "UPI";
      bankModeFields.style.display = isUPI ? "none" : "block";
      upiModeFields.style.display = isUPI ? "block" : "none";
    });
  });

  togglePin.addEventListener("click", () => {
    const show = authCode.type === "password";
    authCode.type = show ? "text" : "password";
    togglePin.textContent = show ? "Hide" : "Show";
  });

  verifyIfsc.addEventListener("click", () => {
    const code = ifsc.value.trim().toUpperCase();
    const prefix = code.slice(0, 4);
    verifyIfsc.disabled = true;
    verifyIfsc.textContent = "Checking...";

    setTimeout(() => {
      bankName.value = ifscMap[prefix] || "Unable to verify IFSC";
      verifyIfsc.disabled = false;
      verifyIfsc.textContent = "Verify IFSC";
    }, 800);
  });

  document.querySelectorAll(".bene").forEach((el) => {
    el.addEventListener("click", () => {
      const data = JSON.parse(el.dataset.bene);
      document.getElementById("beneficiaryName").value = data.name;
      document.getElementById("accountNumber").value = data.account;
      document.getElementById("confirmAccountNumber").value = data.account;
      ifsc.value = data.ifsc;
      const prefix = data.ifsc.slice(0, 4);
      bankName.value = ifscMap[prefix] || "External Bank";
    });
  });

  function setError(id, msg) {
    const target = document.querySelector('[data-error-for="' + id + '"]');
    if (target) target.textContent = msg || "";
  }

  function validate() {
    [
      "fromAccount",
      "beneficiaryName",
      "accountNumber",
      "confirmAccountNumber",
      "ifsc",
      "upiId",
      "upiBeneficiary",
      "amount",
      "purpose",
      "authCode"
    ].forEach((f) => setError(f, ""));

    let ok = true;
    const fromAccount = document.getElementById("fromAccount").value.trim();
    const amount = Number(document.getElementById("amount").value);
    const purpose = document.getElementById("purpose").value.trim();

    if (!fromAccount) {
      setError("fromAccount", "Select source account.");
      ok = false;
    }

    if (mode === "UPI") {
      const upiId = document.getElementById("upiId").value.trim();
      const upiBeneficiary = document.getElementById("upiBeneficiary").value.trim();
      if (!upiId || !upiId.includes("@")) {
        setError("upiId", "Enter a valid UPI ID.");
        ok = false;
      }
      if (!upiBeneficiary) {
        setError("upiBeneficiary", "Enter beneficiary name.");
        ok = false;
      }
    } else {
      const beneficiaryName = document.getElementById("beneficiaryName").value.trim();
      const accountNumber = document.getElementById("accountNumber").value.trim();
      const confirmAccountNumber = document.getElementById("confirmAccountNumber").value.trim();
      const ifscCode = ifsc.value.trim();
      if (!beneficiaryName) {
        setError("beneficiaryName", "Enter beneficiary name.");
        ok = false;
      }
      if (!accountNumber || accountNumber.length < 8) {
        setError("accountNumber", "Account number must be at least 8 digits.");
        ok = false;
      }
      if (accountNumber !== confirmAccountNumber) {
        setError("confirmAccountNumber", "Account numbers do not match.");
        ok = false;
      }
      if (!ifscCode || ifscCode.length < 8) {
        setError("ifsc", "Enter valid IFSC code.");
        ok = false;
      }
    }

    if (!amount || amount <= 0) {
      setError("amount", "Enter transfer amount.");
      ok = false;
    }
    if (!purpose) {
      setError("purpose", "Select transfer purpose.");
      ok = false;
    }
    if (!authCode.value.trim()) {
      setError("authCode", "Enter transaction PIN/OTP.");
      ok = false;
    }

    return ok;
  }

  function generateRef() {
    return "NEXA" + Date.now().toString().slice(-8) + Math.floor(Math.random() * 90 + 10);
  }

  transferForm.addEventListener("submit", (e) => {
    e.preventDefault();
    if (!validate()) return;

    const submitBtn = document.getElementById("submitTransfer");
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="loading"></span> Processing...';

    setTimeout(() => {
      const beneficiary = mode === "UPI" ? document.getElementById("upiBeneficiary").value : document.getElementById("beneficiaryName").value;
      const amount = Number(document.getElementById("amount").value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      const ref = generateRef();
      successDetails.innerHTML = `
        <p><strong>Mode:</strong> ${mode}</p>
        <p><strong>Beneficiary:</strong> ${beneficiary}</p>
        <p><strong>Amount:</strong> $${amount}</p>
        <p><strong>From:</strong> ${document.getElementById("fromAccount").value}</p>
        <p><strong>Purpose:</strong> ${document.getElementById("purpose").value}</p>
        <p><strong>Reference:</strong> ${ref}</p>
      `;
      overlay.classList.add("show");
      submitBtn.disabled = false;
      submitBtn.textContent = "Transfer Funds";
    }, 2200);
  });

  newTransferBtn.addEventListener("click", () => {
    overlay.classList.remove("show");
    transferForm.reset();
    bankName.value = "";
  });
})();
