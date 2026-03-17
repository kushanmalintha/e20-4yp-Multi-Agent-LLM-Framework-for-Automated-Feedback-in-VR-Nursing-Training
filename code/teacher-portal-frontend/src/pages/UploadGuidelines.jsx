import { useState } from "react";

import { uploadGuideline } from "../api/backend.js";

export default function UploadGuidelines() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [status, setStatus] = useState({ type: "", message: "" });
  const [uploading, setUploading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!selectedFile) {
      setStatus({ type: "error", message: "Choose a .txt file first." });
      return;
    }

    setUploading(true);
    setStatus({ type: "", message: "" });

    try {
      const response = await uploadGuideline(selectedFile);
      setStatus({
        type: "success",
        message: `${response.message}. File ID: ${response.file_id}`,
      });
    } catch (err) {
      setStatus({
        type: "error",
        message: err.response?.data?.detail || err.message || "Upload failed",
      });
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="page-grid">
      <div className="page-header">
        <div>
          <h1>Upload Guidelines</h1>
          <p>Upload plain text clinical guideline files to the shared vector store.</p>
        </div>
      </div>

      {status.message && <div className={`status ${status.type}`}>{status.message}</div>}

      <form className="panel upload-box" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="guideline_file">Upload .txt file</label>
          <input
            id="guideline_file"
            type="file"
            accept=".txt,text/plain"
            onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
          />
        </div>

        <div className="button-row">
          <button className="btn btn-primary" type="submit" disabled={uploading}>
            {uploading ? "Uploading..." : "Upload Guidelines"}
          </button>
        </div>
      </form>
    </section>
  );
}
