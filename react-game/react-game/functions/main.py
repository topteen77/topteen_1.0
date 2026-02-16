# Firebase Cloud Functions for Stream Comparison Game
from firebase_functions import https_fn
from firebase_functions.options import set_global_options
from firebase_admin import initialize_app
import typing_extensions as typing
from typing import Dict, Any
from google.cloud.secretmanager_v1 import SecretManagerServiceClient
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

import os
# Initialize Firebase Admin
initialize_app()

# Set global options for cost control
set_global_options(max_instances=10)

def get_secret(secret_name: str, project_id: str = None) -> str:
    """Retrieve a secret from Secret Manager"""
    if project_id is None:
        # Get project ID from environment or use default
        project_id = os.environ.get('GCLOUD_PROJECT', 'your-project-id')
    
    client = SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")



PARAMETER_LABELS = {
    "job_placement": "Job Placement Rate", "job_security": "Job Security",
    "fees_cost": "Fees/Cost", "location": "Location Availability",
    "career_growth": "Career Growth Potential", "industry_demand": "Industry Demand"
}

class StreamScores(typing.TypedDict):
    job_placement: str
    job_security: str
    fees_cost: str
    location: str
    career_growth: str
    industry_demand: str

class StreamDetails(typing.TypedDict):
    name: str
    scores: StreamScores
    strengths: list[str]
    weaknesses: list[str]

class DetailsDict(typing.TypedDict):
    stream1: StreamDetails
    stream2: StreamDetails

class ComparisonResponse(typing.TypedDict):
    winner: str
    reasoning: str
    details: DetailsDict


@https_fn.on_call()
def compareStreams(data: https_fn.CallableRequest) -> Dict[str, Any]:
    try:
        # Get Gemini API key from Secret Manager
        GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
        # Firebase callable functions provide data directly (already unwrapped)
        data = data.data if data.data else {}
        
        print(f"Received data keys: {list(data.keys()) if data else 'None'}")
        
        # Validate required fields
        streams = data.get("streams", [])
        parameters = data.get("parameters", [])
        
        print(f"Extracted streams: {streams}, parameters: {parameters}")
        
        if not isinstance(streams, list) or len(streams) != 2:
            print(f"Validation failed: streams is not a list of 2 items. Type: {type(streams)}, Length: {len(streams) if isinstance(streams, list) else 'N/A'}")
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Invalid streams. Expected array of exactly 2 streams."
            )
        
        if not isinstance(parameters, list) or len(parameters) == 0:
            print(f"Validation failed: parameters is not a non-empty list. Type: {type(parameters)}, Length: {len(parameters) if isinstance(parameters, list) else 'N/A'}")
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Invalid parameters. Expected non-empty array of parameters."
            )
        
        print("Validation passed")
        stream1, stream2 = streams[0], streams[1]
        print(f"Stream1: {stream1}, Stream2: {stream2}")
        
        # Check if Gemini API key is configured - DEMO MODE: Continue even without API key
        print(f"Checking GEMINI_API_KEY. Is set: {GEMINI_API_KEY is not None}, Length: {len(GEMINI_API_KEY) if GEMINI_API_KEY else 0}")
        if not GEMINI_API_KEY:
            print("GEMINI_API_KEY is not configured - Using demo mode")
            # Return demo response immediately (no need to try LLM)
            demo_result = {
                "winner": stream1,  # Always use first stream for demo
                "reasoning": f"Demo mode as api key not found: Based on the selected parameters ({', '.join(parameters)}), {stream1} has been selected as the winner. This is a demonstration response.",
                "details": {
                    "stream1": {
                        "name": stream1,
                        "scores": {param: "8/10" for param in parameters},
                        "strengths": [f"Strong performance in {param.replace('_', ' ')}" for param in parameters],
                        "weaknesses": ["Limited data available for detailed analysis"]
                    },
                    "stream2": {
                        "name": stream2,
                        "scores": {param: "7/10" for param in parameters},
                        "strengths": [f"Good performance in {param.replace('_', ' ')}" for param in parameters],
                        "weaknesses": ["Limited data available for detailed analysis"]
                    }
                }
            }
            return demo_result
        
        # Lazy import and configure Gemini API (inside function to avoid container startup issues)
        print("Starting Gemini import and configuration...")
        try:
            print("Importing google.generativeai...")
            import google.generativeai as genai
            print("Import successful, configuring API key...")
            genai.configure(api_key=GEMINI_API_KEY)
            print("Gemini API configured successfully")
        except ImportError as e:
            print(f"ImportError occurred: {str(e)}")
            import traceback
            print(f"ImportError traceback: {traceback.format_exc()}")
            # Return demo result instead of error
            demo_result = {
                "winner": stream1,
                "reasoning": f"Demo mode import error for gen ai: Based on the selected parameters ({', '.join(parameters)}), {stream1} has been selected as the winner. This is a demonstration response.",
                "details": {
                    "stream1": {
                        "name": stream1,
                        "scores": {param: "8/10" for param in parameters},
                        "strengths": [f"Strong performance in {param.replace('_', ' ')}" for param in parameters],
                        "weaknesses": ["Limited data available for detailed analysis"]
                    },
                    "stream2": {
                        "name": stream2,
                        "scores": {param: "7/10" for param in parameters},
                        "strengths": [f"Good performance in {param.replace('_', ' ')}" for param in parameters],
                        "weaknesses": ["Limited data available for detailed analysis"]
                    }
                }
            }
            return demo_result
        except Exception as e:
            # DEMO MODE: If Gemini configuration fails, return demo response
            print(f"Exception during Gemini configuration: {type(e).__name__}: {str(e)} - Using demo mode")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            
            # Return demo response with first stream as winner
            demo_result = {
                "winner": stream1,  # Always use first stream for demo
                "reasoning": f"Demo mode exception during gemini configuration: Based on the selected parameters ({', '.join(parameters)}), {stream1} has been selected as the winner. This is a demonstration response.",
                "details": {
                    "stream1": {
                        "name": stream1,
                        "scores": {param: "8/10" for param in parameters},
                        "strengths": [f"Strong performance in {param.replace('_', ' ')}" for param in parameters],
                        "weaknesses": ["Limited data available for detailed analysis"]
                    },
                    "stream2": {
                        "name": stream2,
                        "scores": {param: "7/10" for param in parameters},
                        "strengths": [f"Good performance in {param.replace('_', ' ')}" for param in parameters],
                        "weaknesses": ["Limited data available for detailed analysis"]
                    }
                }
            }
            
            return demo_result
            
        param_descs = [PARAMETER_LABELS.get(p, p.replace("_", " ").title()) for p in parameters]
        prompt = f"""Compare {stream1} vs {stream2} based on: {', '.join(param_descs)}.
        Determine winner, provide reasoning (2-3 paragraphs), and detailed scores/strengths/weaknesses for both.
        Winner must be exactly "{stream1}" or "{stream2}"."""
        
        try:
            from google.generativeai import protos
    
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                tools=[protos.Tool(google_search=protos.Tool.GoogleSearch())]
            )
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=ComparisonResponse
                )
            )
            import json
            result = json.loads(response.text)
            if result.get("winner") not in [stream1, stream2]:
                result["winner"] = stream1
            return result
            
        except Exception as e:
            # DEMO MODE: Ignore LLM errors and return demo response with first stream as winner
            error_message = str(e)
            error_type = type(e).__name__
            print(f"Gemini API error ({error_type}): {error_message} - Using demo mode")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            
            # Return demo response with first stream as winner (ignore error)
            demo_result = {
                "winner": stream1,  # Always use first stream for demo
                "reasoning": f"Demo mode gemini result generation failed: Based on the selected parameters ({', '.join(parameters)}), {stream1} has been selected as the winner. This is a demonstration response.",
                "details": {
                    "stream1": {
                        "name": stream1,
                        "scores": {param: "8/10" for param in parameters},
                        "strengths": [f"Strong performance in {param.replace('_', ' ')}" for param in parameters],
                        "weaknesses": ["Limited data available for detailed analysis"]
                    },
                    "stream2": {
                        "name": stream2,
                        "scores": {param: "7/10" for param in parameters},
                        "strengths": [f"Good performance in {param.replace('_', ' ')}" for param in parameters],
                        "weaknesses": ["Limited data available for detailed analysis"]
                    }
                }
            }
            
            return demo_result
    
    except Exception as e:
        # DEMO MODE: Catch-all error handler - return demo response
        error_message = str(e)
        error_type = type(e).__name__
        print(f"Unhandled error ({error_type}): {error_message} - Using demo mode")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Try to get streams from the data if available
        try:
            if not data:
                data = {}
            streams = data.get("streams", [])
            if isinstance(streams, list) and len(streams) >= 2:
                stream1 = streams[0]
                stream2 = streams[1]
                parameters = data.get("parameters", [])
            else:
                stream1 = "Stream 1"
                stream2 = "Stream 2"
                parameters = []
        except:
            stream1 = "Stream 1"
            stream2 = "Stream 2"
            parameters = []
        
        # Return demo response with first stream as winner
        demo_result = {
            "winner": stream1,  # Always use first stream for demo
            "reasoning": f"Demo mode General error: Based on the selected parameters ({', '.join(parameters) if parameters else 'general criteria'}), {stream1} has been selected as the winner. This is a demonstration response.",
            "details": {
                "stream1": {
                    "name": stream1,
                    "scores": {param: "8/10" for param in parameters} if parameters else {},
                    "strengths": [f"Strong performance in {param.replace('_', ' ')}" for param in parameters] if parameters else ["Strong overall performance"],
                    "weaknesses": ["Limited data available for detailed analysis"]
                },
                "stream2": {
                    "name": stream2,
                    "scores": {param: "7/10" for param in parameters} if parameters else {},
                    "strengths": [f"Good performance in {param.replace('_', ' ')}" for param in parameters] if parameters else ["Good overall performance"],
                    "weaknesses": ["Limited data available for detailed analysis"]
                }
            }
        }
        
        return demo_result


class CourseEligibilityRequest(typing.TypedDict):
    educationBackground: Dict[str, Any]
    winnerStream: str

class CourseEligibilityResponse(typing.TypedDict):
    courses: list[str]


@https_fn.on_call()
def checkCourseEligibility(data: https_fn.CallableRequest) -> Dict[str, Any]:
    try:
        # Get Gemini API key from Secret Manager
        GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
        # Firebase callable functions provide data directly (already unwrapped)
        data = data.data if data.data else {}
        
        print(f"Received course eligibility data keys: {list(data.keys()) if data else 'None'}")
        
        # Validate required fields
        education_background = data.get("educationBackground", {})
        winner_stream = data.get("winnerStream", "")
        
        print(f"Education background: {education_background}, Winner stream: {winner_stream}")
        
        if not education_background or not isinstance(education_background, dict):
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Invalid educationBackground. Expected a dictionary."
            )
        
        if not winner_stream or not isinstance(winner_stream, str):
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Invalid winnerStream. Expected a string."
            )
        
        # Check if Gemini API key is configured - DEMO MODE: Continue even without API key
        print(f"Checking GEMINI_API_KEY. Is set: {GEMINI_API_KEY is not None}, Length: {len(GEMINI_API_KEY) if GEMINI_API_KEY else 0}")
        if not GEMINI_API_KEY:
            print("GEMINI_API_KEY is not configured - Using demo mode")
            # Return demo response
            demo_result = {
                "courses": [
                    f"Bachelor's in {winner_stream}",
                    f"Diploma in {winner_stream}",
                    f"Certificate Course in {winner_stream}"
                ]
            }
            return demo_result
        
        # Lazy import and configure Gemini API
        print("Starting Gemini import and configuration...")
        try:
            print("Importing google.generativeai...")
            import google.generativeai as genai
            print("Import successful, configuring API key...")
            genai.configure(api_key=GEMINI_API_KEY)
            print("Gemini API configured successfully")
        except ImportError as e:
            print(f"ImportError occurred: {str(e)}")
            import traceback
            print(f"ImportError traceback: {traceback.format_exc()}")
            # Return demo result
            demo_result = {
                "courses": [
                    f"Bachelor's in {winner_stream}",
                    f"Diploma in {winner_stream}",
                    f"Certificate Course in {winner_stream}"
                ]
            }
            return demo_result
        except Exception as e:
            print(f"Exception during Gemini configuration: {type(e).__name__}: {str(e)} - Using demo mode")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            
            demo_result = {
                "courses": [
                    f"Bachelor's in {winner_stream}",
                    f"Diploma in {winner_stream}",
                    f"Certificate Course in {winner_stream}"
                ]
            }
            return demo_result
        
        # Build prompt for course eligibility
        background_info = education_background.get("background", "")
        stream_info = education_background.get("stream", "")
        specific_area = education_background.get("specificArea", "")
        
        prompt = f"""Based on the following education background and winner stream, provide a list of courses the student is eligible for.

            Education Background: {background_info}
            Stream: {stream_info}
            Specific Area: {specific_area}
            Winner Stream (Career Path): {winner_stream}

            Provide a JSON response with a list of eligible courses. Include undergraduate, diploma, and certificate courses that match the education background and are relevant to the winner stream.

            Return only a JSON object with a "courses" array containing course names as strings."""

        try:
            from google.generativeai import protos
    
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                tools=[protos.Tool(google_search=protos.Tool.GoogleSearch())]
            )
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=CourseEligibilityResponse
                )
            )
            import json
            result = json.loads(response.text)
            
            # Ensure courses is a list
            if not isinstance(result.get("courses"), list):
                result["courses"] = [
                    f"Bachelor's in {winner_stream}",
                    f"Diploma in {winner_stream}"
                ]
            
            return result
            
        except Exception as e:
            # DEMO MODE: Return demo response on error
            error_message = str(e)
            error_type = type(e).__name__
            print(f"Gemini API error ({error_type}): {error_message} - Using demo mode")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            
            demo_result = {
                "courses": [
                    f"Bachelor's in {winner_stream}",
                    f"Diploma in {winner_stream}",
                    f"Certificate Course in {winner_stream}"
                ]
            }
            return demo_result
    
    except Exception as e:
        # DEMO MODE: Catch-all error handler
        error_message = str(e)
        error_type = type(e).__name__
        print(f"Unhandled error ({error_type}): {error_message} - Using demo mode")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Try to get winner stream from data
        try:
            if not data:
                data = {}
            winner_stream = data.get("winnerStream", "the selected field")
        except:
            winner_stream = "the selected field"
        
        # Return demo response
        demo_result = {
            "courses": [
                f"Bachelor's in {winner_stream}",
                f"Diploma in {winner_stream}",
                f"Certificate Course in {winner_stream}"
            ]
        }
        
        return demo_result


# Email sending function using AWS SES SMTP
class SendEmailRequest(typing.TypedDict):
    to: str
    from_email: str
    subject: str
    text: str
    html: str

class SendEmailResponse(typing.TypedDict):
    success: bool
    message: str
    messageId: str


@https_fn.on_call()
def sendEmail(data: https_fn.CallableRequest) -> Dict[str, Any]:
    """
    Send email using AWS SES SMTP
    """
    try:
        # Extract data from request
        request_data = data.data if data.data else {}
        
        # Validate required fields
        to_email = request_data.get("to", "")
        from_email = request_data.get("from", "")
        subject = request_data.get("subject", "")
        text_body = request_data.get("text", "")
        html_body = request_data.get("html", "")
        
        print(f"Sending email to: {to_email}, from: {from_email}, subject: {subject}")
        
        if not to_email:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Recipient email address is required"
            )
        
        if not from_email:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Sender email address is required"
            )
        
        if not subject:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Email subject is required"
            )
        
        if not text_body and not html_body:
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message="Email body (text or HTML) is required"
            )
        
        # AWS SES SMTP Configuration
        SMTP_HOST = 'email-smtp.ap-south-1.amazonaws.com'
        SMTP_PORT = 587
        SMTP_USERNAME = 'AKIA6ODUZGXOTA3W7C6A'
        SMTP_PASSWORD = 'BKEJsYkct8iFoDyd/+G6Bg1qNB2sVCvIKbgmvLbbmck3'
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        
        # Add text and HTML parts
        if text_body:
            text_part = MIMEText(text_body, 'plain')
            msg.attach(text_part)
        
        if html_body:
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
        
        # Send email via AWS SES SMTP
        server = None
        try:
            print(f"Connecting to SMTP server: {SMTP_HOST}:{SMTP_PORT}")
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.set_debuglevel(1)  # Enable debug logging to see SMTP responses
            
            print("Starting TLS...")
            server.starttls()
            
            print("Logging in to SMTP server...")
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            print("SMTP login successful")
            
            # Use sendmail() instead of send_message() for better error handling
            print(f"Sending email from {from_email} to {to_email}")
            print(f"Subject: {subject}")
            
            # Convert message to string for sendmail
            from_addr = from_email
            to_addrs = [to_email]
            msg_string = msg.as_string()
            
            # Send email and capture response
            refused = server.sendmail(from_addr, to_addrs, msg_string)
            
            if refused:
                error_msg = f"SMTP server refused recipients: {refused}"
                print(f"ERROR: {error_msg}")
                raise https_fn.HttpsError(
                    code=https_fn.FunctionsErrorCode.INTERNAL,
                    message=error_msg
                )
            
            print(f"SMTP sendmail() completed successfully")
            print(f"Email accepted by SMTP server for delivery to {to_email}")
            
            server.quit()
            server = None
            
            print(f"Email sent successfully to {to_email}")
            print(f"NOTE: If email is not received, check:")
            print(f"  1. AWS SES account is in sandbox mode (only verified emails can receive)")
            print(f"  2. Recipient email ({to_email}) is verified in AWS SES")
            print(f"  3. Sender email ({from_email}) is verified in AWS SES")
            print(f"  4. Check spam/junk folder")
            
            return {
                "success": True,
                "message": "Email sent successfully (accepted by SMTP server)",
                "messageId": f"ses-{int(time.time())}",
                "note": "If email not received, verify recipient email in AWS SES (sandbox mode restriction)"
            }
            
        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f"SMTP recipients refused: {str(e)}"
            print(f"SMTP ERROR (RecipientsRefused): {error_msg}")
            print(f"This usually means the recipient email is not verified in AWS SES sandbox mode")
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message=f"Recipient email rejected by AWS SES: {error_msg}. Verify the email address in AWS SES Console."
            )
        except smtplib.SMTPSenderRefused as e:
            error_msg = f"SMTP sender refused: {str(e)}"
            print(f"SMTP ERROR (SenderRefused): {error_msg}")
            print(f"This usually means the sender email is not verified in AWS SES")
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
                message=f"Sender email rejected by AWS SES: {error_msg}. Verify {from_email} in AWS SES Console."
            )
        except smtplib.SMTPDataError as e:
            error_msg = f"SMTP data error: {str(e)}"
            print(f"SMTP ERROR (DataError): {error_msg}")
            print(f"This usually means AWS SES rejected the email content or recipient")
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INTERNAL,
                message=f"AWS SES rejected the email: {error_msg}"
            )
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            error_code = getattr(e, 'smtp_code', None)
            error_response = getattr(e, 'smtp_error', None)
            print(f"SMTP ERROR: {error_msg}")
            print(f"SMTP Code: {error_code}, Response: {error_response}")
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INTERNAL,
                message=f"SMTP error: {error_msg}"
            )
        except Exception as e:
            error_msg = f"Error sending email: {str(e)}"
            error_type = type(e).__name__
            print(f"ERROR ({error_type}): {error_msg}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise https_fn.HttpsError(
                code=https_fn.FunctionsErrorCode.INTERNAL,
                message=error_msg
            )
        finally:
            # Ensure SMTP connection is closed
            if server:
                try:
                    server.quit()
                except:
                    pass
    
    except https_fn.HttpsError:
        # Re-raise HttpsError as-is
        raise
    except Exception as e:
        # Catch any other errors
        error_message = str(e)
        error_type = type(e).__name__
        print(f"Unhandled error ({error_type}): {error_message}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        raise https_fn.HttpsError(
            code=https_fn.FunctionsErrorCode.INTERNAL,
            message=f"Failed to send email: {error_message}"
        )
