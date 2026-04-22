// App.jsx -- Root component
import { useState } from "react";
import FileUpload from "./components/FileUpload";
import ReviewStep from "./components/ReviewStep";
import GradingForm from "./components/GradingForm";

export default function App() {
  // uploadData  : raw parse result from /api/upload (sentence_groups)
  // gradingData : cleaned/confirmed sentences built by ReviewStep
  const [uploadData, setUploadData]   = useState(null);
  const [gradingData, setGradingData] = useState(null);

  const handleUploadSuccess = (data) => {
    setUploadData(data);
    setGradingData(null);
  };

  const handleReviewConfirm = (cleanedData) => {
    setGradingData(cleanedData);
  };

  const handleReset = () => {
    setUploadData(null);
    setGradingData(null);
  };

  if (!uploadData) {
    return <FileUpload onUploadSuccess={handleUploadSuccess} />;
  }

  if (!gradingData) {
    return (
      <ReviewStep
        uploadData={uploadData}
        onConfirm={handleReviewConfirm}
        onReset={handleReset}
      />
    );
  }

  return <GradingForm uploadData={gradingData} onReset={handleReset} />;
}

