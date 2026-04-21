// App.jsx -- Root component
import { useState } from "react";
import FileUpload from "./components/FileUpload";
import GradingForm from "./components/GradingForm";

export default function App() {
  const [uploadData, setUploadData] = useState(null);

  const handleUploadSuccess = (data) => setUploadData(data);
  const handleReset = () => setUploadData(null);

  if (!uploadData) {
    return <FileUpload onUploadSuccess={handleUploadSuccess} />;
  }
  return <GradingForm uploadData={uploadData} onReset={handleReset} />;
}
