import { useState, useEffect } from 'react';
import './Frame4_1.css';

// Generate random patient ID
const generatePatientId = () => {
  const num = Math.floor(Math.random() * 9000) + 1000;
  return `P${num}`;
};

// Generate realistic vital signs within normal/abnormal ranges
const generateVitals = (riskLevel = 'normal') => {
  const ranges = {
    normal: {
      heartRate: { min: 60, max: 100 },
      systolicBP: { min: 110, max: 130 },
      diastolicBP: { min: 70, max: 85 },
      respiratoryRate: { min: 12, max: 18 },
      oxygenSat: { min: 96, max: 100 },
      temperature: { min: 36.5, max: 37.2 }
    },
    elevated: {
      heartRate: { min: 85, max: 110 },
      systolicBP: { min: 125, max: 145 },
      diastolicBP: { min: 80, max: 95 },
      respiratoryRate: { min: 16, max: 22 },
      oxygenSat: { min: 94, max: 98 },
      temperature: { min: 37.0, max: 38.2 }
    },
    high: {
      heartRate: { min: 100, max: 130 },
      systolicBP: { min: 140, max: 180 },
      diastolicBP: { min: 90, max: 110 },
      respiratoryRate: { min: 20, max: 30 },
      oxygenSat: { min: 88, max: 95 },
      temperature: { min: 37.5, max: 39.5 }
    }
  };

  const r = ranges[riskLevel] || ranges.normal;
  
  return {
    heartRate: Math.round(Math.random() * (r.heartRate.max - r.heartRate.min) + r.heartRate.min),
    systolicBP: Math.round(Math.random() * (r.systolicBP.max - r.systolicBP.min) + r.systolicBP.min),
    diastolicBP: Math.round(Math.random() * (r.diastolicBP.max - r.diastolicBP.min) + r.diastolicBP.min),
    respiratoryRate: Math.round(Math.random() * (r.respiratoryRate.max - r.respiratoryRate.min) + r.respiratoryRate.min),
    oxygenSat: Math.round(Math.random() * (r.oxygenSat.max - r.oxygenSat.min) + r.oxygenSat.min),
    temperature: parseFloat((Math.random() * (r.temperature.max - r.temperature.min) + r.temperature.min).toFixed(1))
  };
};

const Frame4_1 = ({ onClose, onAdd }) => {
  const [formData, setFormData] = useState({
    patientId: '',
    heartRate: '',
    systolicBP: '',
    diastolicBP: '',
    respiratoryRate: '',
    oxygenSat: '',
    temperature: '',
    arrivalMode: 'Walk-in',
    acuityLevel: '3',
    riskProfile: 'normal'
  });
  
  const [errors, setErrors] = useState({});
  const [toast, setToast] = useState({ show: false, message: '', type: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const vitals = generateVitals('normal');
    setFormData(prev => ({
      ...prev,
      patientId: generatePatientId(),
      ...vitals
    }));
  }, []);

  const handleRiskProfileChange = (e) => {
    const riskProfile = e.target.value;
    const vitals = generateVitals(riskProfile);
    setFormData(prev => ({ ...prev, riskProfile, ...vitals }));
  };

  const regenerateId = () => {
    setFormData(prev => ({ ...prev, patientId: generatePatientId() }));
  };

  const regenerateVitals = () => {
    const vitals = generateVitals(formData.riskProfile);
    setFormData(prev => ({ ...prev, ...vitals }));
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.patientId.trim()) newErrors.patientId = 'Patient ID is required';
    
    const hr = parseInt(formData.heartRate);
    if (isNaN(hr) || hr < 30 || hr > 200) newErrors.heartRate = 'Must be 30-200 bpm';
    
    const sbp = parseInt(formData.systolicBP);
    if (isNaN(sbp) || sbp < 70 || sbp > 250) newErrors.systolicBP = 'Must be 70-250 mmHg';
    
    const dbp = parseInt(formData.diastolicBP);
    if (isNaN(dbp) || dbp < 40 || dbp > 150) newErrors.diastolicBP = 'Must be 40-150 mmHg';
    if (dbp >= sbp) newErrors.diastolicBP = 'Must be less than systolic';
    
    const rr = parseInt(formData.respiratoryRate);
    if (isNaN(rr) || rr < 8 || rr > 40) newErrors.respiratoryRate = 'Must be 8-40 /min';
    
    const o2 = parseInt(formData.oxygenSat);
    if (isNaN(o2) || o2 < 70 || o2 > 100) newErrors.oxygenSat = 'Must be 70-100%';
    
    const temp = parseFloat(formData.temperature);
    if (isNaN(temp) || temp < 35 || temp > 42) newErrors.temperature = 'Must be 35-42°C';
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const showToast = (message, type = 'success') => {
    setToast({ show: true, message, type });
    setTimeout(() => setToast({ show: false, message: '', type: '' }), 3000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) {
      showToast('Please fix validation errors', 'error');
      return;
    }
    
    setIsSubmitting(true);
    try {
      // No time field - backend will use latest hospital time from DB
      const newPatient = {
        id: formData.patientId.toUpperCase(),
        heartRate: parseInt(formData.heartRate),
        systolicBP: parseInt(formData.systolicBP),
        diastolicBP: parseInt(formData.diastolicBP),
        respiratoryRate: parseInt(formData.respiratoryRate),
        oxygenSat: parseInt(formData.oxygenSat),
        temperature: parseFloat(formData.temperature),
        arrivalMode: formData.arrivalMode,
        acuityLevel: parseInt(formData.acuityLevel),
      };
      
      await onAdd(newPatient);
      showToast(`Patient ${newPatient.id} added successfully!`, 'success');
      setTimeout(() => onClose(), 1000);
    } catch (err) {
      showToast(`Failed to add patient: ${err.message}`, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOverlayClick = (e) => {
    if (e.target.classList.contains('add-patient-overlay')) onClose();
  };

  return (
    <div className="add-patient-overlay" onClick={handleOverlayClick}>
      <div className="add-patient-popup">
        <button className="close-btn" onClick={onClose}>×</button>
        <h2 className="popup-title">Add New Patient</h2>
        
        {toast.show && <div className={`toast ${toast.type}`}>{toast.message}</div>}
        
        <form onSubmit={handleSubmit} className="patient-form">
          <div className="risk-profile-selector">
            <label>Risk Profile:</label>
            <select name="riskProfile" value={formData.riskProfile} onChange={handleRiskProfileChange}>
              <option value="normal">Normal (Low Risk)</option>
              <option value="elevated">Elevated (Moderate)</option>
              <option value="high">High Risk</option>
            </select>
            <button type="button" className="regenerate-btn" onClick={regenerateVitals}>🔄 Regenerate</button>
          </div>

          <table className="form-table">
            <thead><tr><th>Field</th><th>Value</th></tr></thead>
            <tbody>
              <tr className={errors.patientId ? 'error-row' : ''}>
                <td className="field-label">Patient ID</td>
                <td>
                  <div className="input-with-button">
                    <input type="text" name="patientId" value={formData.patientId} onChange={handleChange} required />
                    <button type="button" className="small-btn" onClick={regenerateId}>🔄</button>
                  </div>
                  {errors.patientId && <span className="error-text">{errors.patientId}</span>}
                </td>
              </tr>
              <tr className={errors.heartRate ? 'error-row' : ''}>
                <td className="field-label">Heart Rate (bpm)</td>
                <td>
                  <input type="number" name="heartRate" value={formData.heartRate} onChange={handleChange} min="30" max="200" required />
                  {errors.heartRate && <span className="error-text">{errors.heartRate}</span>}
                </td>
              </tr>
              <tr className={errors.systolicBP ? 'error-row' : ''}>
                <td className="field-label">Systolic BP (mmHg)</td>
                <td>
                  <input type="number" name="systolicBP" value={formData.systolicBP} onChange={handleChange} min="70" max="250" required />
                  {errors.systolicBP && <span className="error-text">{errors.systolicBP}</span>}
                </td>
              </tr>
              <tr className={errors.diastolicBP ? 'error-row' : ''}>
                <td className="field-label">Diastolic BP (mmHg)</td>
                <td>
                  <input type="number" name="diastolicBP" value={formData.diastolicBP} onChange={handleChange} min="40" max="150" required />
                  {errors.diastolicBP && <span className="error-text">{errors.diastolicBP}</span>}
                </td>
              </tr>
              <tr className={errors.respiratoryRate ? 'error-row' : ''}>
                <td className="field-label">Respiratory Rate (/min)</td>
                <td>
                  <input type="number" name="respiratoryRate" value={formData.respiratoryRate} onChange={handleChange} min="8" max="40" required />
                  {errors.respiratoryRate && <span className="error-text">{errors.respiratoryRate}</span>}
                </td>
              </tr>
              <tr className={errors.oxygenSat ? 'error-row' : ''}>
                <td className="field-label">Oxygen Saturation (%)</td>
                <td>
                  <input type="number" name="oxygenSat" value={formData.oxygenSat} onChange={handleChange} min="70" max="100" required />
                  {errors.oxygenSat && <span className="error-text">{errors.oxygenSat}</span>}
                </td>
              </tr>
              <tr className={errors.temperature ? 'error-row' : ''}>
                <td className="field-label">Temperature (°C)</td>
                <td>
                  <input type="number" name="temperature" value={formData.temperature} onChange={handleChange} step="0.1" min="35" max="42" required />
                  {errors.temperature && <span className="error-text">{errors.temperature}</span>}
                </td>
              </tr>
              <tr>
                <td className="field-label">Arrival Mode</td>
                <td>
                  <select name="arrivalMode" value={formData.arrivalMode} onChange={handleChange} required>
                    <option value="Walk-in">Walk-in</option>
                    <option value="Ambulance">Ambulance</option>
                  </select>
                </td>
              </tr>
              <tr>
                <td className="field-label">Acuity Level</td>
                <td>
                  <select name="acuityLevel" value={formData.acuityLevel} onChange={handleChange} required>
                    <option value="1">1 - Resuscitation</option>
                    <option value="2">2 - Emergent</option>
                    <option value="3">3 - Urgent</option>
                    <option value="4">4 - Less Urgent</option>
                    <option value="5">5 - Non-Urgent</option>
                  </select>
                </td>
              </tr>
            </tbody>
          </table>

          <div className="form-actions">
            <button type="button" className="cancel-btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="add-btn" disabled={isSubmitting}>
              {isSubmitting ? 'Adding...' : 'Add Patient'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Frame4_1;
