import React, { useState, useRef } from 'react';
import { UploadCloud, FileArchive, CheckCircle2, AlertTriangle, ArrowLeft, Loader2 } from 'lucide-react';
import { api } from '../api/client';

export default function UploadModal({ onUploadSuccess, onCancel }) {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile) => {
    setError(null);
    if (!selectedFile.name.toLowerCase().endsWith('.zip')) {
      setError('Please select a valid .zip archive.');
      return;
    }
    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      const result = await api.uploadProject(file);
      onUploadSuccess(result);
    } catch (err) {
      setError(err.message || 'Upload failed. Ensure the backend server is running.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <button
        onClick={onCancel}
        className="inline-flex items-center space-x-2 text-sm text-slate-400 hover:text-white mb-6 transition"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Back to Projects</span>
      </button>

      <div className="bg-slate-900/80 border border-slate-800 rounded-3xl p-8 shadow-2xl">
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-white tracking-tight">Upload Code Repository</h2>
          <p className="text-sm text-slate-400 mt-2">
            Upload your project as a ZIP file. The system will unpack, parse ASTs, and construct the dependency graph offline.
          </p>
        </div>

        {/* Drag & Drop Zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200 ${
            isDragging
              ? 'border-brand-500 bg-brand-500/10'
              : 'border-slate-700/80 hover:border-slate-500 bg-slate-950/50 hover:bg-slate-900/50'
          }`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".zip"
            className="hidden"
          />

          <div className="h-16 w-16 mx-auto rounded-2xl bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center mb-4">
            <UploadCloud className="h-8 w-8" />
          </div>

          <p className="text-base font-medium text-white mb-1">
            Drag and drop your ZIP archive here, or <span className="text-brand-400 underline">browse</span>
          </p>
          <p className="text-xs text-slate-500">Supports standard Python repository ZIP archives up to 50 MB</p>
        </div>

        {/* Selected File Card */}
        {file && (
          <div className="mt-6 p-4 bg-slate-800/60 border border-slate-700/80 rounded-xl flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <FileArchive className="h-6 w-6 text-brand-400" />
              <div>
                <p className="text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-slate-400">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
              </div>
            </div>
            <CheckCircle2 className="h-5 w-5 text-emerald-400" />
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="mt-6 p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl flex items-start space-x-3 text-rose-300 text-sm">
            <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-rose-200">Upload Rejected</p>
              <p className="text-xs text-rose-300/90 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="mt-8 flex items-center justify-end space-x-3">
          <button
            onClick={onCancel}
            disabled={uploading}
            className="px-5 py-2.5 rounded-xl border border-slate-700 text-slate-300 hover:text-white hover:bg-slate-800 text-sm font-medium transition"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className={`inline-flex items-center space-x-2 px-6 py-2.5 rounded-xl text-white text-sm font-medium shadow-lg transition ${
              !file || uploading
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                : 'bg-brand-600 hover:bg-brand-500 shadow-brand-500/20 active:scale-95'
            }`}
          >
            {uploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Processing & Scanning...</span>
              </>
            ) : (
              <span>Start Analysis</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
