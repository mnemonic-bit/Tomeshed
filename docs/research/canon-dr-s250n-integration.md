# Canon DR-S250N as a document source

Research date: 2026-10-31. Status: completed for documentation research. Hardware verification: not_run; the scanner was not available to this session.

## Result and model assumption

Yes, the Canon **imageFORMULA DR-S250N** can supply scanned documents directly to a server. Canon documents standalone delivery to a shared folder, FTP, FTPS, SFTP, email, or a printer, without a scanning computer. The user supplied the name `DN-S250N`; this report assumes the intended model is `DR-S250N`, which is the model named in Canon's documentation. Confirm the scanner's label before configuring an integration. [Canon product page](https://my.canon/en/consumer/imageformula-dr-s250n/main/product?category=scanning&subCategory=)

## Access choices

| Access method | Documented behavior | Integration implication |
| --- | --- | --- |
| Standalone scanner job | The scanner sends files to a configured destination. | Recommended: receive PDF files in a server inbox, then import and process completed files. |
| CaptureOnTouch Lite Web | An embedded browser application provides scanning without installing drivers or scanning software. Open the scanner's IP address in a browser on the network. | Suitable for interactive scanning; browser access alone does not establish a supported API for Tomeshed to control. |
| ISIS/TWAIN driver | Canon supplies Windows drivers for compatible applications; a Mac TWAIN driver is also listed. | An application on a supported computer can control acquisition. |
| Canon SDK | Canon offers DR Scanner SDK and imageFORMULA Web Scan SDK. | Custom scan control is possible in principle, subject to SDK access, supported platforms, and a local bridge. |

Sources: [Canon direct destinations](https://my.canon/en/consumer/imageformula-dr-s250n/main/product?category=scanning&subCategory=), [Canon Europe browser scanning and USB/Ethernet specifications](https://www.canon-europe.com/business/products/scanners/document-scanners/imageformula-dr-s250n/specifications/), [Canon driver listings](https://www.canon.co.nz/other-products/imageformula-dr-s250n/support?option=drivers), [Canon developer tools](https://canon.jp/biz/product/office-device/imageformula/developers).

Canon's manual describes shared-folder credentials, host, path, domain/workgroup, and a connection test. The shared-folder interface is consistent with an SMB share; the reviewed passages do not establish an exact SMB protocol version. SFTP is independently listed as a supported direct destination, so an SFTP inbox avoids that uncertainty. [Canon manual, output settings](https://gdlp01.c-wss.com/gds/5/0300047785/03/DR-S250N_User_Manual_EN.pdf), [Canon direct destinations](https://my.canon/en/consumer/imageformula-dr-s250n/main/product?category=scanning&subCategory=)

## PDF and structured output

The scanner supports PDF output with multiple pages in one file. Its `Add OCR information` setting recognizes text and adds text data to a PDF; select the document's recognition language. Without OCR, a scanned PDF can contain page images without usable text. Canon also documents TIFF output. [Canon manual, CaptureOnTouch Lite Web output settings and scanner-job output settings](https://gdlp01.c-wss.com/gds/5/0300047785/03/DR-S250N_User_Manual_EN.pdf)

Docling is the processing stage after acquisition. Docling accepts PDFs and images and exports structured JSON and Markdown. Keep the original PDF for faithful reading and retain Docling output for search, extraction, or downstream processing. [Docling formats](https://docling-project.github.io/docling/usage/supported_formats/)

Recommended design, rather than a claim about an existing Tomeshed integration:

```text
Paper → DR-S250N → PDF over SFTP/shared folder → server inbox
     → import completed PDF → retain source PDF
     → Docling OCR and layout analysis → JSON + Markdown
```

Use a 300 dpi duplex scan as an initial trial setting, then assess small text, tables, page order, and blank-page handling with representative documents. In the proposed receiver, import only completed transfers and prevent repeated imports. These are integration recommendations, not verified scanner or Tomeshed behavior.

The current Docling CLI documentation gives the following command shape:

```bash
docling convert --ocr --to json --to md --output ./converted ./scan.pdf
```

For German and English OCR through Tesseract, configure the Tesseract OCR engine and install the `deu` and `eng` language data. Confirm the installed Docling version's CLI options before deployment. Command verification: not_run locally. [Docling CLI](https://docling-project.github.io/docling/reference/cli/), [Docling OCR configuration](https://docling-project.github.io/docling/concepts/OCR/)

## Limits and next checks

No public, documented driverless REST API for arbitrary Tomeshed scan commands was established by this research. Canon's Web Scan SDK is a separate route: Canon documents ScanServer and scanner-driver installation for SDK operation. Canon's listed ScanServer platforms include Windows and Windows Server. Linux acquisition through a Canon driver, SANE, or eSCL remains unverified. Receiving files over SFTP or a shared folder does not require a Linux scanner driver. [Canon ScanServer requirements](https://faq.canon.jp/app/answers/detail/a_id/105444/), [Canon ScanServer platform listing](https://www.canon.com.au/support/sims-content?cid=904C261E64B04D088AC346D4562E29CF&ctype=ap&pid=dab92473f2934d72971eddb1152f27f3)

Firmware can affect browser features and authentication behavior; Canon's firmware history records changes to output formats and SFTP authentication. Match configuration steps to the device's installed firmware. No firmware update was performed. [Canon firmware history](https://asia.canon/en/support/0400888922)

The next verification is a physical test: confirm the model and firmware, configure a PDF job to an SFTP or shared-folder inbox, scan representative pages, confirm complete delivery, and inspect both PDF text and Docling JSON. Scan initiation from the Tomeshed UI would require a separate integration decision and SDK/platform test. No application code or version change is part of this report.
