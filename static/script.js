// =============================
// Fungsi untuk switch antar mode
// =============================
function showMode(mode) {

  document.getElementById('mode-pca').classList.add('hidden');
  document.getElementById('mode-raw').classList.add('hidden');
  document.getElementById('mode-manual').classList.add('hidden');

  document.getElementById('mode-' + mode).classList.remove('hidden');

  document.getElementById('resultsSection').classList.add('hidden');
  document.getElementById('predictionResultsContainer').innerHTML = '';

  document.getElementById('errorMessage').style.display = 'none';
  document.getElementById('loadingMessage').style.display = 'none';
}


// =============================
// Helper tampilkan hasil prediksi
// =============================
function displayResults(results) {

  const resultsSection = document.getElementById('resultsSection');
  const container = document.getElementById('predictionResultsContainer');

  resultsSection.classList.remove('hidden');
  container.innerHTML = '';

  if (!results || results.length === 0) {
    container.innerHTML = '<p>Tidak ada hasil prediksi.</p>';
    return;
  }

  results.forEach((item, index) => {

    const probability = item.fraud_probability ?? 0;

    const isFraud = probability >= 0.25;

    const statusClass = isFraud ? 'fraud' : 'non-fraud';
    const statusText = isFraud ? 'FRAUDULENT' : 'LEGITIMATE';

    container.innerHTML += `
      <div class="result-item">

        <div>
          <p><strong>Transaksi ${index + 1}:</strong></p>
          <p>
            <strong>Status:</strong> 
            <span class="${statusClass}">
              ${statusText}
            </span>
          </p>
        </div>

        <div>
          <p>
            <strong>Fraud Probability:</strong> 
            ${(probability * 100).toFixed(2)}%
          </p>
          <p><em>(Threshold: 25%)</em></p>
        </div>

      </div>
    `;
  });

}


// =============================
// Fungsi umum untuk fetch API
// =============================
async function fetchPrediction(url, options, singleResult = false) {

  const loadingMessage = document.getElementById('loadingMessage');
  const errorMessage = document.getElementById('errorMessage');
  const resultsSection = document.getElementById('resultsSection');

  loadingMessage.style.display = 'block';
  errorMessage.style.display = 'none';
  resultsSection.classList.add('hidden');

  try {

    const res = await fetch(url, options);
    const data = await res.json();

    loadingMessage.style.display = 'none';

    if (!res.ok) {
      errorMessage.innerText = 'Error: ' + (data.error || 'Terjadi kesalahan pada backend');
      errorMessage.style.display = 'block';
      return;
    }

    if (singleResult) {
      displayResults([data]);
    } else {
      displayResults(data.results);
    }

  } catch (err) {

    console.error('Fetch error:', err);

    loadingMessage.style.display = 'none';
    errorMessage.innerText = 'Gagal terhubung ke backend.';
    errorMessage.style.display = 'block';

  }
}


// =============================
// Mode A: Upload PCA CSV
// =============================
document.getElementById('formPcaCsv').addEventListener('submit', async (e) => {

  e.preventDefault();

  const file = e.target.querySelector('input[type=file]').files[0];

  if (!file) {
    alert('Pilih file CSV terlebih dahulu!');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  await fetchPrediction(
    '/predict_pca_csv',
    {
      method: 'POST',
      body: formData
    }
  );

});


// =============================
// Mode B: Upload Raw CSV
// =============================
document.getElementById('formRawCsv').addEventListener('submit', async (e) => {

  e.preventDefault();

  const file = e.target.querySelector('input[type=file]').files[0];

  if (!file) {
    alert('Pilih file CSV terlebih dahulu!');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  await fetchPrediction(
   '/predict_raw_csv',
    {
      method: 'POST',
      body: formData
    }
  );

});


// =============================
// Mode C: Manual Input
// =============================
document.getElementById("timeInput").addEventListener("input", function(e){

  let value = e.target.value.replace(/[^\d.]/g,"");

  const parts = value.split(".");
  if(parts.length > 2){
    value = parts[0] + "." + parts[1];
  }

  e.target.value = value;

});

document.getElementById("amountInput").addEventListener("input", function(e){

  let value = e.target.value.replace(/\D/g,"");

  value = new Intl.NumberFormat("id-ID").format(value);

  e.target.value = value;

});

document.getElementById('formManual').addEventListener('submit', async (e) => {

  e.preventDefault();

  const formData = new FormData(e.target);
  const jsonData = Object.fromEntries(formData.entries());

  // Convert number fields
  jsonData.TransactionID = Number(jsonData.TransactionID);
  jsonData.Time = Number(jsonData.Time);

  // Bersihkan format angka Indonesia (1.900.000) sebelum konversi ke Number
  // Hapus semua titik pemisah ribuan, lalu konversi ke angka
  const rawAmount = String(jsonData.Amount).replace(/\./g, '').replace(/,/g, '.');
  jsonData.Amount = Number(rawAmount);

  await fetchPrediction(
   '/predict_manual',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(jsonData)
    },
    true
  );

});