import plivo
import os

def send_sms(client,src_ph=os.environ.get('PLIVO_NUM'),dst_ph='+918340647358', msg='Hello, demo messages from Plivo API'):
    """
    Sends an SMS using Plivo API.

    Args:
        client (plivo.RestClient): Plivo REST client.
        src_ph (str): Source phone number.
        dst_ph (str): Destination phone number.
        msg (str): Message content.

    Returns:
        plivo.response.Response: Response object from Plivo.
    """
    response = client.messages.create(
    src=src_ph,
    dst=dst_ph,
    text=msg,)
    # print(response)
    return response

def get_client():
    """
    Creates and returns a Plivo REST client.

    Returns:
        plivo.RestClient: Plivo REST client.
    """
    cl = plivo.RestClient(os.environ['PLIVO_AUTH_ID'],os.environ['PLIVO_AUTH_TOKEN'])
    return cl

