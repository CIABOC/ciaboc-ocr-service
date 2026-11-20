# Spring Boot Integration Guide

## Architecture

```
React Frontend
      │
      ▼
Spring Boot Backend  ←── Authorization, business rules, database
      │
      │  POST /api/v1/ocr/extract
      │  Header: X-API-Key: <secret>
      │  Body: multipart/form-data (file)
      ▼
FastAPI OCR Service  ←── Text extraction only
      │
      ▼
JSON Response
      │
      ▼
Spring Boot Backend
      │
      ▼
Receptionist Reviews & Corrects Data
      │
      ▼
Visitor Registration (PostgreSQL)
```

## API Contract

### Endpoint

```
POST http://<ocr-host>:8000/api/v1/ocr/extract
```

### Request

- **Method:** POST
- **Content-Type:** multipart/form-data
- **Header:** `X-API-Key: <configured-api-key>`
- **Body:** `file` — JPEG or PNG image, max 10 MB
- **Query (optional):** `document_type=NIC|PASSPORT|DRIVING_LICENCE`

### Response (200 OK)

```json
{
  "status": "success",
  "message": "Document text extracted successfully.",
  "document": {
    "format": "JPEG",
    "width": 1200,
    "height": 800
  },
  "ocr_result": {
    "language": "en",
    "lines": [
      {"text": "NATIONAL IDENTITY CARD", "confidence": 0.99},
      {"text": "NIC No: 912345678V", "confidence": 0.98}
    ]
  },
  "extraction": {
    "classification": {
      "document_type": "NIC",
      "confidence": 0.75,
      "evidence": ["NIC label text", "Old-format NIC number pattern"]
    },
    "nic": {
      "nic_number": {"value": "912345678V", "raw_text": "NIC No: 912345678V", "confidence": 0.98, "needs_verification": true},
      "full_name": {"value": "KAMAL PERERA", "raw_text": "Name: KAMAL PERERA", "confidence": 0.97, "needs_verification": true},
      "date_of_birth": {"value": "1991-05-15", "raw_text": null, "confidence": null, "needs_verification": true},
      "gender": {"value": "Male", "raw_text": null, "confidence": null, "needs_verification": true},
      "address": {"value": null, "raw_text": null, "confidence": null, "needs_verification": true},
      "nic_format": "old"
    },
    "passport": null,
    "driving_licence": null,
    "raw_text": ["NATIONAL IDENTITY CARD", "NIC No: 912345678V", "Name: KAMAL PERERA"],
    "extraction_notes": []
  },
  "processing_time_ms": 234.5,
  "verification_required": true
}
```

## Java Client — RestTemplate

```java
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

@Service
public class OcrClient {

    private final RestTemplate restTemplate;

    @Value("${ciaboc.ocr.url}")
    private String ocrServiceUrl;

    @Value("${ciaboc.ocr.api-key}")
    private String apiKey;

    public OcrClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public OcrResponse extractDocument(MultipartFile file) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        headers.set("X-API-Key", apiKey);

        ByteArrayResource resource = new ByteArrayResource(file.getBytes()) {
            @Override
            public String getFilename() {
                return file.getOriginalFilename();
            }
        };

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new HttpEntity<>(resource, createFileHeaders(file)));

        HttpEntity<MultiValueMap<String, Object>> request =
            new HttpEntity<>(body, headers);

        ResponseEntity<OcrResponse> response = restTemplate.exchange(
            ocrServiceUrl + "/api/v1/ocr/extract",
            HttpMethod.POST,
            request,
            OcrResponse.class
        );

        return response.getBody();
    }

    private HttpHeaders createFileHeaders(MultipartFile file) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.parseMediaType(
            file.getContentType() != null ? file.getContentType() : "image/jpeg"
        ));
        return headers;
    }
}
```

## Java Client — WebClient (Reactive)

```java
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.http.client.MultipartBodyBuilder;

@Service
public class OcrWebClient {

    private final WebClient webClient;

    public OcrWebClient(
            @Value("${ciaboc.ocr.url}") String ocrUrl,
            @Value("${ciaboc.ocr.api-key}") String apiKey) {
        this.webClient = WebClient.builder()
            .baseUrl(ocrUrl)
            .defaultHeader("X-API-Key", apiKey)
            .build();
    }

    public Mono<OcrResponse> extractDocument(MultipartFile file) {
        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("file", file.getResource());

        return webClient.post()
            .uri("/api/v1/ocr/extract")
            .bodyValue(builder.build())
            .retrieve()
            .bodyToMono(OcrResponse.class)
            .timeout(Duration.ofSeconds(30));
    }
}
```

## Spring Boot Configuration

```yaml
# application.yml
ciaboc:
  ocr:
    url: http://localhost:8000
    api-key: ${CIABOC_OCR_API_KEY}
    timeout-seconds: 30
    max-file-size-mb: 10
```

## Error Handling

| OCR Status | Spring Boot Action |
|------------|-------------------|
| 200 | Present extracted fields to receptionist |
| 400 | Show "Invalid image" message |
| 413 | Show "File too large" message |
| 429 | Retry after delay |
| 503 | Retry after delay |
| 500 | Show generic error, log for investigation |
| Timeout | Show "OCR service unavailable" |

## Important Rules

1. **Never trust OCR output directly** — always present to receptionist for verification
2. **Spring Boot handles authorization** — the OCR service does not check user roles
3. **Spring Boot handles database** — the OCR service never accesses PostgreSQL
4. **Spring Boot handles audit** — log visitor registration events in Spring Boot
5. **Timeout:** Set a 30-second timeout on the HTTP client
6. **Max upload:** Validate file size in Spring Boot before sending to OCR
