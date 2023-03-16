import django
from django.contrib.auth.models import User
from store.models import Address, Cart, Category, Order, Product
from django.shortcuts import redirect, render, get_object_or_404
from .forms import RegistrationForm, AddressForm
from django.contrib import messages
from django.views import View
import decimal
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator # for Class Based Views
from django.http import JsonResponse
from django.conf import settings
import json
import stripe
import openai
import uuid
from django.views.decorators.csrf import csrf_exempt
from decouple import config


# Create your views here.

def home(request):
    categories = Category.objects.filter(is_active=True, is_featured=True)[:3]
    products = Product.objects.filter(is_active=True, is_featured=True)[:8]
    context = {
        'categories': categories,
        'products': products,
    }
    return render(request, 'store/index.html', context)


def detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related_products = Product.objects.exclude(id=product.id).filter(is_active=True, category=product.category)
    context = {
        'product': product,
        'related_products': related_products,

    }
    return render(request, 'store/detail.html', context)


def all_categories(request):
    categories = Category.objects.filter(is_active=True)
    return render(request, 'store/categories.html', {'categories':categories})


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(is_active=True, category=category)
    categories = Category.objects.filter(is_active=True)
    context = {
        'category': category,
        'products': products,
        'categories': categories,
    }
    return render(request, 'store/category_products.html', context)

def set_session_data(request):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        address_id = data.get('address_id')
        print("hello")
        print(address_id)
        request.session['address_id'] = address_id
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'success': False})


# Authentication Starts Here

class RegistrationView(View):
    def get(self, request):
        form = RegistrationForm()
        return render(request, 'account/register.html', {'form': form})
    
    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            messages.success(request, "Congratulations! Registration Successful!")
            form.save()
        return render(request, 'account/register.html', {'form': form})
        

@login_required
def profile(request):
    addresses = Address.objects.filter(user=request.user)
    orders = Order.objects.filter(user=request.user)
    return render(request, 'account/profile.html', {'addresses':addresses, 'orders':orders})


@method_decorator(login_required, name='dispatch')
class AddressView(View):
    def get(self, request):
        form = AddressForm()
        return render(request, 'account/add_address.html', {'form': form})

    def post(self, request):
        form = AddressForm(request.POST)
        if form.is_valid():
            user=request.user
            locality = form.cleaned_data['locality']
            city = form.cleaned_data['city']
            state = form.cleaned_data['state']
            reg = Address(user=user, locality=locality, city=city, state=state)
            reg.save()
            messages.success(request, "New Address Added Successfully.")
        return redirect('store:profile')

@login_required
def wishlist(request):
     print("hello")



@login_required
def remove_address(request, id):
    a = get_object_or_404(Address, user=request.user, id=id)
    a.delete()
    messages.success(request, "Address removed.")
    return redirect('store:profile')

@login_required
def add_to_cart(request):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    user = request.user
    product_id = request.GET.get('prod_id')
    product = get_object_or_404(Product, id=product_id)

    # Check whether the Product is alread in Cart or Not
    item_already_in_cart = Cart.objects.filter(product=product_id, user=user)
    if item_already_in_cart:
        cp = get_object_or_404(Cart, product=product_id, user=user)
        cp.quantity += 1
        cp.save()
    else:
        Cart(user=user, product=product).save()
    
    return redirect('store:cart')


@login_required
def cart(request):
    user = request.user
    cart_products = Cart.objects.filter(user=user)

    # Display Total on Cart Page
    amount = decimal.Decimal(0)
    shipping_amount = decimal.Decimal(10)
    # using list comprehension to calculate total amount based on quantity and shipping
    cp = [p for p in Cart.objects.all() if p.user==user]
    if cp:
        for p in cp:
            temp_amount = (p.quantity * p.product.price)
            amount += temp_amount

    # Customer Addresses
    addresses = Address.objects.filter(user=user)

    context = {
        'cart_products': cart_products,
        'amount': amount,
        'shipping_amount': shipping_amount,
        'total_amount': amount + shipping_amount,
        'publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        'addresses': addresses,
    }
    return render(request, 'store/cart.html', context)


@login_required
def remove_cart(request, cart_id):
    if request.method == 'GET':
        c = get_object_or_404(Cart, id=cart_id)
        c.delete()
        messages.success(request, "Product removed from Cart.")
    return redirect('store:cart')


@login_required
def plus_cart(request, cart_id):
    if request.method == 'GET':
        cp = get_object_or_404(Cart, id=cart_id)
        cp.quantity += 1
        cp.save()
    return redirect('store:cart')


@login_required
def minus_cart(request, cart_id):
    if request.method == 'GET':
        cp = get_object_or_404(Cart, id=cart_id)
        # Remove the Product if the quantity is already 1
        if cp.quantity == 1:
            cp.delete()
        else:
            cp.quantity -= 1
            cp.save()
    return redirect('store:cart')


@login_required
def checkout(request):
    user = request.user
    address_id = request.session.get('address_id')
    print(address_id)
    for key, value in request.session.items():
        print(f"{key}: {value}")
    
    address = get_object_or_404(Address, id=address_id)
    # Get all the products of User in Cart
    cart = Cart.objects.filter(user=user)
    for c in cart:
        # Saving all the products from Cart to Order
        Order(user=user, address=address, product=c.product, quantity=c.quantity).save()
        # And Deleting from Cart
        c.delete()
    return redirect('store:orders')


@login_required
def orders(request):
    all_orders = Order.objects.filter(user=request.user).order_by('-ordered_date')
    return render(request, 'store/orders.html', {'orders': all_orders})


openai.api_key = config('OPEN_API_KEY')
model_engine = "text-davinci-002"


@csrf_exempt
def chat_view(request):
    if request.method == "POST":
            data = json.loads(request.body)
            prompt = data.get("message")
            print("next line is the message")
            print(prompt)
            print(type((request.POST.get("message"))))
            print(type(prompt))
            completions = openai.Completion.create(
                engine=model_engine,
                prompt=prompt,
                max_tokens=3097,
                n=1,
                stop=None,
                temperature=0.5,
            )

            message = completions.choices[0].text
            print(message)
            return JsonResponse({"response": message})
    return render(request, "store/chat.html")

    # if request.method == "POST":
    #     # Get the user's message from the request data
    #     message = request.POST.get("message")
    #
    #     # # Add the user's message to the conversation object
    #     # openai.api.Conversation.create(
    #     #     engine="davinci",
    #     #     prompt=message,
    #     #     conversation_id=conversation_id,
    #     # )
    #
    #     # Generate a response from the ChatGPT module
    #     response = openai.Completion.create(
    #         engine="davinci",
    #         prompt=f"Reply: {message}\n",
    #         max_tokens=1024,
    #         temperature=0.5,
    #         n=1,
    #         stop=None,
    #     )
    #
    #     # Get the generated response from the API response
    #     text = response.choices[0].text.strip()
    #
    #     # Return the response to the client
    #     return JsonResponse({"response": text})
    #
    # else:
    #     # If the request method is not POST, return an error response
    #     return JsonResponse({"error": "Invalid request method"})



def shop(request):
    return render(request, 'store/shop.html')





def test(request):
    return render(request, 'store/test.html')
